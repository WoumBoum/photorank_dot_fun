// Ultra-minimalist PhotoRank app

class PhotoRankApp {
    constructor() {
        this.ws = null;
        this.currentPair = null;
        // Prevent rapid double-submits
        this._voteInFlight = false;
        this._voteCooldown = false;
        this.init();
    }

    init() {
        this.setupWebSocket();
        this.setupEventListeners();
        this.loadInitialData();
        this.handleAuthRedirect();
        // Top logo theming handled via <picture> element and prefers-color-scheme
    }

    handleAuthRedirect() {
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');
        if (token) {
            localStorage.setItem('token', token);
            window.history.replaceState({}, document.title, window.location.pathname);
            // Update navigation immediately after login
            if (window.updateNavigation) {
                window.updateNavigation();
            }
        }
    }

    isAuthenticated() {
        return localStorage.getItem('token') !== null;
    }

    async makeAuthenticatedRequest(url, options = {}) {
        const token = localStorage.getItem('token');
        if (!token) {
            window.location.href = '/login';
            return Promise.reject(new Error('No token available'));
        }

        const headers = {
            ...options.headers,
            'Authorization': `Bearer ${token}`
        };

        const response = await fetch(url, {
            ...options,
            headers
        });

        if (response.status === 401 || response.status === 403) {
            // Token expired or invalid - clear and redirect with user-friendly message
            localStorage.removeItem('token');

            // Show a brief message before redirect
            const message = document.createElement('div');
            message.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #000;
                color: #fff;
                padding: 1rem 1.5rem;
                border-radius: 4px;
                z-index: 1000;
                font-family: 'Courier New', monospace;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            `;
            message.textContent = 'Session expired. Redirecting to login...';
            document.body.appendChild(message);

            setTimeout(() => {
                document.body.removeChild(message);
                window.location.href = '/login';
            }, 2000);

            return Promise.reject(new Error('Authentication required'));
        }

        return response;
    }

    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        console.log('Connecting to WebSocket:', wsUrl);

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('WebSocket connected successfully');
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'new_pair') {
                    this.displayNewPair(data);
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            this.ws.onclose = (event) => {
                console.log('WebSocket closed:', event.code, event.reason);
            };
        } catch (error) {
            console.error('Error loading stats:', error);
            const grid = document.getElementById('stats-grid');
            if (grid) {
                grid.innerHTML = '<p>Error loading stats. Please try refreshing the page.</p>';
            }
        }
    }

    setupEventListeners() {
        // Theme change observer not needed for logo anymore (handled by <picture> + prefers-color-scheme)
        // Keyboard voting (left/right arrows)
        document.addEventListener('keydown', (e) => {
            // Ignore when typing in inputs/textareas or if no pair loaded
            const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
            if (tag === 'input' || tag === 'textarea' || tag === 'select' || !this.currentPair) return;

            if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                e.preventDefault();
                // Debounce rapid repeats while a vote is being processed by disabling during fade
                if (this._keyboardVotingLocked || this._voteInFlight || this._voteCooldown) return;
                this._keyboardVotingLocked = true;

                const container = document.getElementById(e.key === 'ArrowLeft' ? 'photo1' : 'photo2');
                if (container) {
                    // Synthesize an event compatible with handleVote
                    const clickLikeEvent = { currentTarget: container };
                    this.handleVote(clickLikeEvent);
                    // Release lock after next pair loads slightly after fade
                    setTimeout(() => { this._keyboardVotingLocked = false; }, 350);
                } else {
                    this._keyboardVotingLocked = false;
                }
            }
        });
        // Photo voting
        document.querySelectorAll('.photo-container').forEach(container => {
            container.addEventListener('click', (e) => this.handleVote(e));
        });

        // File upload
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('file-input');

        if (uploadArea && fileInput) {
            uploadArea.addEventListener('click', () => fileInput.click());
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                this.handleFilesUpload(e.dataTransfer.files);
            });
            fileInput.addEventListener('change', (e) => {
                this.handleFilesUpload(e.target.files);
            });
        }

        // Delete button delegation scoped strictly to stats page (photo delete)
        document.addEventListener('click', (e) => {
            const pathNow = window.location.pathname || '';
            const onStats = pathNow === '/stats';
            if (!onStats) return; // avoid intercepting delete buttons on other pages (e.g., categories, leaderboard)
            const target = e.target;
            if (target && target.classList && target.classList.contains('delete-btn') && target.dataset && target.dataset.photoId) {
                e.preventDefault();
                e.stopPropagation();
                const photoId = target.dataset.photoId;
                this.deletePhoto(photoId, target);
            }
        });
    }

    async loadInitialData() {
        const path = window.location.pathname;
        if (path === '/' || /\/[^/]+\/vote$/.test(path)) {
            await this.loadPhotoPair();
            // Show guest vote counter if not authenticated
            if (!this.isAuthenticated()) {
                await this.updateGuestVoteCounter();
            }
        } else if (path === '/leaderboard' || /\/[^/]+\/leaderboard$/.test(path)) {
            // If URL is /{category}/leaderboard, prefer path-based API
            const m = path.match(/^\/([^/]+)\/leaderboard\/?$/);
            const categoryName = m ? decodeURIComponent(m[1]) : null;
            // Only load leaderboard if we have a category OR we are exactly on /leaderboard
            if (categoryName) {
                await this.loadLeaderboard(categoryName);
            } else if (path === '/leaderboard') {
                await this.loadLeaderboard(null);
            }
        } else if (path === '/stats') {
            await this.loadStats();
            this.initPseudonymEditor();
        }
    }

    async loadPhotoPair() {
        try {
            // Always hide the no-choices message and show photos when making a new request
            this.hideNoMoreChoices();

            const endpoint = this.isAuthenticated() ? '/api/photos/pair/session' : '/api/photos/pair/session';
            const fetchFn = this.isAuthenticated() ? (u,o)=>this.makeAuthenticatedRequest(u,o) : (u,o)=>fetch(u, o);
            const response = await fetchFn(endpoint, {
                credentials: 'include',
                cache: 'no-cache' // Ensure fresh data
            });

            if (response.status === 400) {
                // No category selected
                window.location.href = '/categories';
                return;
            }

            if (response.status === 410) {
                // No more pairs to vote on
                this.showNoMoreChoices();
                return;
            }

            if (!response.ok) {
                console.error('HTTP Error:', response.status, response.statusText);
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.displayNewPair(data);
        } catch (error) {
            if (error.message !== 'Authentication required') {
                console.error('Error loading photos:', error);
                const votingContainer = document.querySelector('.voting-container');
                if (votingContainer) {
                    votingContainer.innerHTML = '<div style="text-align: center; padding: 2rem;"><h2>Error loading photos</h2><p>Please try refreshing the page or check your connection.</p></div>';
                }
            }
        }
    }

    hideNoMoreChoices() {
        const noChoicesMessage = document.getElementById('no-choices-message');
        if (noChoicesMessage) {
            noChoicesMessage.style.display = 'none';
        }

        // Show photo containers
        const container1 = document.getElementById('photo1');
        const container2 = document.getElementById('photo2');
        if (container1) container1.style.display = 'block';
        if (container2) container2.style.display = 'block';
    }

    displayNewPair(data) {
        if (!data || !data.photos || data.photos.length !== 2) return;

        this.currentPair = data.photos;
        // set per-pair nonce to avoid stale clicks during rerender
        this._pairNonce = `${this.currentPair[0]?.id || 'x'}-${this.currentPair[1]?.id || 'y'}-${Date.now()}`;

        const img1 = document.getElementById('img1');
        const img2 = document.getElementById('img2');
        const container1 = document.getElementById('photo1');
        const container2 = document.getElementById('photo2');
        const noChoicesMessage = document.getElementById('no-choices-message');

        if (img1 && img2 && container1 && container2) {
            // Hide no choices message if it exists
            if (noChoicesMessage) {
                noChoicesMessage.style.display = 'none';
            }

            // Reset all styles before loading new images
            container1.style.opacity = '1';
            container2.style.opacity = '1';
            container1.style.display = 'block';
            container2.style.display = 'block';
            img1.style.opacity = '0';
            img2.style.opacity = '0';

            img1.src = `/api/photos/${data.photos[0].filename}`;
            img2.src = `/api/photos/${data.photos[1].filename}`;

            // Add fade effect
            setTimeout(() => {
                img1.style.opacity = '1';
                img2.style.opacity = '1';
            }, 50);

            // Update progress display if available
            this.updateProgressDisplay(
                data.progress,
                data.progress_percentage,
                data.votes_until_important,
                data.is_important_match,
                data.photo1_rank,
                data.photo2_rank
            );

            // Show important match UI if applicable
            if (data.is_important_match) {
                this.showImportantMatchUI(data.photo1_rank, data.photo2_rank);
            } else {
                this.hideImportantMatchUI();
            }
        }
    }

    updateProgressDisplay(progressText, progressPercentage, votesUntilImportant, isImportantMatch, photo1Rank, photo2Rank) {
        // Find or create progress container
        let progressContainer = document.getElementById('voting-progress');
        if (!progressContainer) {
            progressContainer = document.createElement('div');
            progressContainer.id = 'voting-progress';
            progressContainer.className = 'progress-container';

            // Insert after the vote question
            const voteQuestion = document.getElementById('vote-question');
            if (voteQuestion && voteQuestion.parentNode) {
                voteQuestion.parentNode.insertBefore(progressContainer, voteQuestion.nextSibling);
            }
        }

        if (progressText && progressPercentage !== undefined) {
            // Build anticipation text for important matches
            let anticipationText = '';
            if (isImportantMatch === true) {
                // On the actual important match, show banner text only (no countdown)
                anticipationText = 'IMPORTANT MATCH! • ';
            } else if (votesUntilImportant !== null && votesUntilImportant !== undefined) {
                if (votesUntilImportant === 1) {
                    anticipationText = 'IMPORTANT MATCH NEXT • ';
                } else if (votesUntilImportant > 1 && votesUntilImportant <= 5) {
                    anticipationText = `IMPORTANT MATCH IN ${votesUntilImportant} VOTES • `;
                }
            }

            // Create progress bar
            let progressBarHTML = `
                <div class="progress-text">${anticipationText}Progress: ${progressText} pairs</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${progressPercentage}%;"></div>
                </div>
                <div class="progress-text" style="margin-top: 0.25rem; font-size: 0.8rem;">${progressPercentage.toFixed(1)}% complete</div>
            `;

            progressContainer.innerHTML = progressBarHTML;

            // Add ticks for important match milestones
            this.addImportantMatchTicks(progressContainer, votesUntilImportant);
        } else {
            progressContainer.innerHTML = '';
        }
    }

    addImportantMatchTicks(progressContainer, votesUntilImportant) {
        if (votesUntilImportant === null || votesUntilImportant === undefined) return;
        const progressBar = progressContainer.querySelector('.progress-bar');
        if (!progressBar) return;

        // Parse total_possible_pairs from the progress text "a/b pairs"
        const header = progressContainer.querySelector('.progress-text');
        if (!header) return;
        const match = header.textContent.match(/Progress:\s*(\d+)\s*\/\s*(\d+)\s*pairs/i);
        if (!match) return;
        const totalPairs = parseInt(match[2], 10);
        if (!totalPairs || totalPairs < 20) return; // no ticks if less than one interval

        const importantMatchInterval = 20; // every 20 votes is important

        // Build vote milestones: 20, 40, 60, ... up to totalPairs (caps at totalPairs)
        for (let v = importantMatchInterval; v <= totalPairs; v += importantMatchInterval) {
            const percent = Math.min(100, (v / totalPairs) * 100);
            const tick = document.createElement('div');
            tick.className = 'progress-tick important-match';
            // Center the tick on its percent position and clamp to bar bounds
            const tickWidthPx = 3; // keep in sync with CSS .progress-tick.important-match width
            const clamped = Math.max(0, Math.min(100, percent));
            tick.style.left = `calc(${clamped}% - ${tickWidthPx / 2}px - 2px)`;
            progressBar.appendChild(tick);

            // Add label each 40 votes for readability; labels are centered via CSS translateX(-50%)
            if (v % 40 === 0) {
                const label = document.createElement('div');
                label.className = 'progress-tick-label';
                label.style.left = `${clamped}%`;
                label.textContent = `${v} votes`;
                progressBar.appendChild(label);
            }
        }
    }

    showImportantMatchUI(photo1Rank, photo2Rank) {
        // Remove any existing important match UI
        this.hideImportantMatchUI();

        // Create important match banner
        const banner = document.createElement('div');
        banner.id = 'important-match-banner';
        banner.className = 'important-match-banner';

        // Add rank information
        banner.innerHTML = `
            IMPORTANT MATCHUP: 
            <strong>#${photo1Rank}</strong> vs <strong>#${photo2Rank}</strong>
        `;

        // Insert before the photo pair
        const photoPair = document.querySelector('.photo-pair');
        if (photoPair && photoPair.parentNode) {
            photoPair.parentNode.insertBefore(banner, photoPair);
        }
    }

    hideImportantMatchUI() {
        const banner = document.getElementById('important-match-banner');
        if (banner) {
            banner.remove();
        }
    }

    showNoMoreChoices() {
        const img1 = document.getElementById('img1');
        const img2 = document.getElementById('img2');
        const container1 = document.getElementById('photo1');
        const container2 = document.getElementById('photo2');

        // Hide photo containers
        if (container1) container1.style.display = 'none';
        if (container2) container2.style.display = 'none';

        // Create or show no choices message
        let noChoicesMessage = document.getElementById('no-choices-message');
        if (!noChoicesMessage) {
            noChoicesMessage = document.createElement('div');
            noChoicesMessage.id = 'no-choices-message';
            noChoicesMessage.className = 'no-choices-message';

            // Derive current category from URL if on "/{category}/vote"
            let categorySegment = null;
            const match = window.location.pathname.match(/^\/([^/]+)\/vote$/);
            if (match) categorySegment = match[1];
            const uploadHref = categorySegment ? `/${encodeURIComponent(categorySegment)}/upload` : '/upload';

            noChoicesMessage.innerHTML = `
                <h2>No more choices to make</h2>
                <p>You've voted on all possible photo combinations in this category.</p>
                <p>You can still vote in other categories or upload new photos.</p>
                <div class="no-choices-actions">
                    <a href="/categories" class="btn">Choose Another Category</a>
                    <a href="${uploadHref}" class="btn">Upload New Photo</a>
                </div>
            `;

            // Insert after the voting container
            const votingContainer = document.querySelector('.voting-container') || document.querySelector('.vote-section');
            if (votingContainer) {
                votingContainer.appendChild(noChoicesMessage);
            } else {
                document.body.appendChild(noChoicesMessage);
            }
        } else {
            noChoicesMessage.style.display = 'block';
        }
    }

    async handleVote(event) {
        if (!this.currentPair) return;
        
        // Check authentication - if not authenticated, use guest voting
        const isAuthenticated = this.isAuthenticated();
        if (!isAuthenticated) {
            await this.handleGuestVote(event);
            return;
        }

        // Block rapid double-submits
        if (this._voteInFlight || this._voteCooldown) return;
        const nonceAtClick = this._pairNonce;
        if (!this.currentPair || nonceAtClick !== this._pairNonce) return;
        this._voteInFlight = true;

        const clickedContainer = event.currentTarget;
        const isFirst = clickedContainer.id === 'photo1';

        const winner = isFirst ? this.currentPair[0] : this.currentPair[1];
        const loser  = isFirst ? this.currentPair[1] : this.currentPair[0];

        try {
            if (!winner?.id || !loser?.id) return;

            // Ensure we are still on the same pair when sending
            if (nonceAtClick !== this._pairNonce) { this._voteInFlight = false; return; }
            await this.makeAuthenticatedRequest('/api/votes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ winner_id: winner.id, loser_id: loser.id })
            });

            // Temporarily disable pointer events on containers during transition
            const c1 = document.getElementById('photo1');
            const c2 = document.getElementById('photo2');
            if (c1) c1.style.pointerEvents = 'none';
            if (c2) c2.style.pointerEvents = 'none';

            // Fade out loser
            const loserContainer = isFirst ? document.getElementById('photo2') : document.getElementById('photo1');
            if (loserContainer) loserContainer.style.opacity = '0.3';

            // Short cooldown to avoid extra clicks during animation
            this._voteCooldown = true;
            setTimeout(() => {
                // prevent stale clicks during fetch/render window
                this.currentPair = null;
                this.loadPhotoPair();
                this._voteCooldown = false;
                if (c1) c1.style.pointerEvents = '';
                if (c2) c2.style.pointerEvents = '';
            }, 250);

        } catch (error) {
            if (error.message !== 'Authentication required') {
                console.error('Error submitting vote:', error);
            }
        } finally {
            this._voteInFlight = false;
        }
    }

    async handleGuestVote(event) {
        if (!this.currentPair) return;
        if (this._voteInFlight || this._voteCooldown) return;
        const nonceAtClick = this._pairNonce;
        if (!this.currentPair || nonceAtClick !== this._pairNonce) return;
        this._voteInFlight = true;

        const clickedContainer = event.currentTarget;
        const isFirst = clickedContainer.id === 'photo1';

        const winner = isFirst ? this.currentPair[0] : this.currentPair[1];
        const loser  = isFirst ? this.currentPair[1] : this.currentPair[0];

        try {
            if (!winner?.id || !loser?.id) return;

            // Ensure we are still on the same pair when sending
            if (nonceAtClick !== this._pairNonce) { this._voteInFlight = false; return; }

            console.log('[GUEST_VOTE] Sending vote request:', {
                winner_id: winner.id,
                loser_id: loser.id,
                session_id: document.cookie.includes('guest_session') ? 'present' : 'none'
            });

            const response = await fetch('/api/votes/guest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ winner_id: winner.id, loser_id: loser.id }),
                credentials: 'include'  // Important for cookies
            });

            console.log('[GUEST_VOTE] Response received:', {
                status: response.status,
                statusText: response.statusText,
                headers: Object.fromEntries(response.headers.entries())
            });

            if (response.status === 429) {
                // Guest vote limit reached
                const errorData = await response.json();
                console.log('[GUEST_VOTE] Rate limit hit:', errorData);
                this.showGuestLimitMessage(errorData.detail);
                this._voteInFlight = false;
                return;
            }

            if (!response.ok) {
                // Try to get detailed error information
                let errorDetails = `HTTP ${response.status}: ${response.statusText}`;
                try {
                    const errorText = await response.text();
                    console.error('[GUEST_VOTE] Error response body:', errorText);
                    try {
                        const errorJson = JSON.parse(errorText);
                        errorDetails += ` - ${errorJson.detail || JSON.stringify(errorJson)}`;
                    } catch {
                        errorDetails += ` - ${errorText}`;
                    }
                } catch (e) {
                    console.error('[GUEST_VOTE] Could not read error response:', e);
                }
                throw new Error(errorDetails);
            }

            const responseData = await response.json();
            console.log('[GUEST_VOTE] Success response:', responseData);

            // Update guest vote counter
            await this.updateGuestVoteCounter();

            // Same UI handling as authenticated votes
            const c1 = document.getElementById('photo1');
            const c2 = document.getElementById('photo2');
            if (c1) c1.style.pointerEvents = 'none';
            if (c2) c2.style.pointerEvents = 'none';

            const loserContainer = isFirst ? document.getElementById('photo2') : document.getElementById('photo1');
            if (loserContainer) loserContainer.style.opacity = '0.3';

            this._voteCooldown = true;
            setTimeout(() => {
                this.currentPair = null;
                this.loadPhotoPair();
                this._voteCooldown = false;
                if (c1) c1.style.pointerEvents = '';
                if (c2) c2.style.pointerEvents = '';
            }, 250);

        } catch (error) {
            console.error('[GUEST_VOTE] Detailed error:', {
                message: error.message,
                stack: error.stack,
                name: error.name
            });
            if (error.message.includes('429')) {
                this.showGuestLimitMessage('Guest vote limit reached. Please sign up to continue voting.');
            }
        } finally {
            this._voteInFlight = false;
        }
    }

    async updateGuestVoteCounter() {
        try {
            const response = await fetch('/api/votes/guest/stats', {
                credentials: 'include'
            });
            
            if (response.ok) {
                const stats = await response.json();
                this.showGuestVoteCounter(stats.remaining_votes);
            }
        } catch (error) {
            console.error('Error updating guest vote counter:', error);
        }
    }

    showGuestVoteCounter(remainingVotes) {
        // Create or update guest vote counter UI
        let counterElement = document.getElementById('guest-vote-counter');
        
        if (!counterElement) {
            counterElement = document.createElement('div');
            counterElement.id = 'guest-vote-counter';
            counterElement.className = 'guest-vote-counter';
            counterElement.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: #000;
                color: #fff;
                padding: 0.5rem 1rem;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 0.9rem;
                z-index: 1000;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            `;
            
            // Insert after the voting container or directly in body
            const votingContainer = document.querySelector('.voting-container') || document.body;
            votingContainer.appendChild(counterElement);
        }
        
        counterElement.textContent = `Guest votes: ${remainingVotes}/10 remaining`;
        
        // Show signup prompt when running low
        if (remainingVotes <= 3) {
            this.showSignupPrompt(remainingVotes);
        }
    }

    showGuestLimitMessage(message) {
        // Remove any existing messages
        this.removeGuestLimitMessage();
        
        const messageElement = document.createElement('div');
        messageElement.id = 'guest-limit-message';
        messageElement.className = 'guest-limit-message';
        messageElement.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #000;
            color: #fff;
            padding: 2rem;
            border-radius: 8px;
            text-align: center;
            font-family: 'Courier New', monospace;
            z-index: 1001;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            max-width: 400px;
            width: 90%;
        `;
        
        messageElement.innerHTML = `
            <h3 style="margin: 0 0 1rem 0;">${message}</h3>
            <p style="margin: 0 0 1.5rem 0;">Sign up to continue voting and track your progress!</p>
            <a href="/login" class="btn" style="display: inline-block; padding: 0.5rem 1.5rem;">Sign Up Now</a>
        `;
        
        document.body.appendChild(messageElement);
        
        // Add overlay
        const overlay = document.createElement('div');
        overlay.id = 'guest-limit-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            z-index: 1000;
        `;
        document.body.appendChild(overlay);
    }

    removeGuestLimitMessage() {
        const message = document.getElementById('guest-limit-message');
        const overlay = document.getElementById('guest-limit-overlay');
        
        if (message) message.remove();
        if (overlay) overlay.remove();
    }

    showSignupPrompt(remainingVotes) {
        // Show subtle signup prompt when votes are running low
        const promptElement = document.getElementById('guest-signup-prompt');
        
        if (!promptElement && remainingVotes > 0) {
            const prompt = document.createElement('div');
            prompt.id = 'guest-signup-prompt';
            prompt.className = 'guest-signup-prompt';
            prompt.style.cssText = `
                position: fixed;
                bottom: 70px;
                right: 20px;
                background: #000;
                color: #fff;
                padding: 0.75rem 1rem;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 0.8rem;
                z-index: 999;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                max-width: 250px;
            `;
            
            prompt.innerHTML = `
                Only ${remainingVotes} guest vote${remainingVotes > 1 ? 's' : ''} left! 
                <a href="/login" style="color: #fff; text-decoration: underline; margin-left: 0.5rem;">Sign up</a>
            `;
            
            document.body.appendChild(prompt);
            
            // Auto-dismiss after 10 seconds
            setTimeout(() => {
                if (prompt.parentNode) {
                    prompt.remove();
                }
            }, 10000);
        }
    }

    async loadLeaderboard(categoryName = null) {
        try {
            let response;
            if (categoryName) {
                // Use path-based leaderboard when category is in URL
                response = await fetch(`/api/photos/leaderboard/${encodeURIComponent(categoryName)}`);
            } else {
                // Fallback to session-based when on plain /leaderboard
                response = await fetch('/api/photos/leaderboard/session', {
                    credentials: 'include' // Important for session cookies
                });
            }

            if (!response.ok) {
                // If session-based call failed due to no category, redirect to picker
                if (!categoryName && response.status === 400) {
                    window.location.href = '/categories';
                    return;
                }
                throw new Error('Failed to load leaderboard');
            }

            const photos = await response.json();
            this.displayLeaderboard(photos);
        } catch (error) {
            console.error('Error loading leaderboard:', error);
        }
    }

    displayLeaderboard(photos) {
        const grid = document.getElementById('leaderboard-grid');
        if (!grid) return;

        grid.innerHTML = '';

        photos.forEach((photo, index) => {
            const card = document.createElement('div');
            card.className = 'photo-card';
            card.innerHTML = `
                <div class="rank">
                    ${index < 3 ? '<span class="crown">👑</span>' : ''}
                    #${index + 1}
                </div>
                <img src="/api/photos/${photo.filename}" alt="Photo ${index + 1}">
                <div class="elo">${Math.round(photo.elo_rating)} ELO</div>
                <div class="uploader">by ${photo.owner_username}</div>
            `;
            grid.appendChild(card);
        });
    }

    async loadStats() {
        if (!this.isAuthenticated()) {
            console.log('[STATS] User not authenticated, redirecting to login');
            window.location.href = '/login';
            return;
        }

        console.log('[STATS] Loading stats for authenticated user');

        try {
            const response = await this.makeAuthenticatedRequest('/api/users/stats');

            console.log('[STATS] Response status:', response.status);

            if (!response.ok) {
                console.error('[STATS] Stats endpoint error:', response.status, response.statusText);
                const errorText = await response.text();
                console.error('[STATS] Error response:', errorText);
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const stats = await response.json();
            console.log('[STATS] Received stats:', stats);
            this.displayStats(stats);
        } catch (error) {
            if (error.message !== 'Authentication required') {
                console.error('[STATS] Error loading stats:', error);
                const grid = document.getElementById('stats-grid');
                if (grid) {
                    grid.innerHTML = '<p>Error loading stats. Please try refreshing the page.</p>';
                }
            }
        }
    }

    // Top logo theming handled by <picture> element with prefers-color-scheme.

    initPseudonymEditor() {
        const input = document.getElementById('pseudo-input');
        const saveBtn = document.getElementById('pseudo-save');
        const status = document.getElementById('pseudo-status');
        if (!input || !saveBtn) return;

        // Preload current username
        this.makeAuthenticatedRequest('/api/users/me').then(r => r.json()).then(me => {
            input.value = me.username || '';
        }).catch(() => { });

        saveBtn.addEventListener('click', async () => {
            const newName = (input.value || '').trim().toLowerCase();
            status.textContent = '';
            if (!/^[a-z0-9_-]{3,20}$/.test(newName)) {
                status.textContent = 'Invalid: 3-20 chars a-z0-9_-';
                return;
            }
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';
            try {
                const resp = await this.makeAuthenticatedRequest('/api/users/me/username', {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: newName })
                });
                if (resp.ok) {
                    status.textContent = 'Saved';
                } else {
                    const err = await resp.json().catch(() => ({}));
                    status.textContent = err.detail || 'Error';
                }
            } catch (e) {
                status.textContent = 'Network error';
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = 'Save';
            }
        });
    }

    displayStats(stats) {
        const grid = document.getElementById('stats-grid');
        if (!grid) return;

        console.log('[STATS] Displaying stats:', stats);

        grid.innerHTML = '';

        if (!stats || !stats.photos || stats.photos.length === 0) {
            console.log('[STATS] No photos found');
            grid.innerHTML = '<p>No photos uploaded yet. <a href="/upload">Upload your first photo</a></p>';
            return;
        }

        console.log(`[STATS] Displaying ${stats.photos.length} photos`);

        stats.photos.forEach(photo => {
            const card = document.createElement('div');
            card.className = 'stat-card';

            const winRate = photo.total_duels > 0 ?
                Math.round((photo.wins / photo.total_duels) * 100) : 0;

            card.innerHTML = `
                <img src="/api/photos/${photo.filename}" alt="Your photo">
                <h3>Rank #${photo.rank}</h3>
                <div class="stat-value">${Math.round(photo.elo_rating)}</div>
                <div class="stat-label">ELO Rating</div>
                <div class="stat-value">${winRate}%</div>
                <div class="stat-label">Win Rate</div>
                <div class="stat-value">${photo.total_duels}</div>
                <div class="stat-label">Duels Fought</div>
                <div class="stat-value">${photo.category_name}</div>
                <div class="stat-label">Category</div>
                <button class="delete-btn" data-photo-id="${photo.id}">Delete</button>
            `;
            grid.appendChild(card);
        });
    }

    async deletePhoto(photoId, buttonElement) {
        if (!confirm('Are you sure you want to delete this photo? This action cannot be undone.')) {
            return;
        }

        const card = buttonElement.closest('.stat-card');
        const originalText = buttonElement.textContent;
        buttonElement.textContent = 'Deleting...';
        buttonElement.disabled = true;

        try {
            const response = await this.makeAuthenticatedRequest(`/api/photos/${photoId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                // Remove the card from the grid with fade effect
                card.style.opacity = '0.5';
                card.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    card.remove();
                    // Reload stats to update counts
                    this.loadStats();
                }, 250);
            } else {
                const error = await response.json();
                alert(`Error: ${error.detail}`);
                buttonElement.textContent = originalText;
                buttonElement.disabled = false;
            }
        } catch (error) {
            if (error.message !== 'Authentication required') {
                console.error('Error deleting photo:', error);
                alert('Failed to delete photo');
                buttonElement.textContent = originalText;
                buttonElement.disabled = false;
            }
        }
    }

    async handleFilesUpload(fileList) {
        const files = Array.from(fileList || []).filter(f => f && f.type && f.type.startsWith('image/'));
        if (files.length === 0) return;

        if (!this.isAuthenticated()) {
            window.location.href = '/login';
            return;
        }

        const status = document.getElementById('upload-status');
        if (status) status.textContent = 'Uploading...';

        // Cap to 10
        const limited = files.slice(0, 10);
        const formData = new FormData();
        for (const f of limited) formData.append('files', f);

        try {
            const response = await this.makeAuthenticatedRequest('/api/photos/upload/session/batch', {
                method: 'POST',
                body: formData,
                credentials: 'include'
            });

            if (response.ok) {
                if (status) status.textContent = `Uploaded ${limited.length} file(s)!`;
                setTimeout(() => {
                    const m = window.location.pathname.match(/^\/([^/]+)\/upload$/);
                    const dest = m ? `/${encodeURIComponent(m[1])}/vote` : '/';
                    window.location.href = dest;
                }, 800);
            } else {
                const result = await response.json().catch(() => ({}));
                if (response.status === 400 && result.detail === 'No category selected') {
                    window.location.href = '/categories';
                } else {
                    if (status) status.textContent = `Error: ${result.detail || 'Upload failed'}`;
                }
            }
        } catch (e) {
            if (status) status.textContent = 'Upload failed';
            console.error('Upload error:', e);
        }
    }
}

// Global debug logging function
window.debugLog = function (message, type = 'info') {
    const debugPanel = document.getElementById('debug-panel');
    if (!debugPanel) {
        console.log(`[DEBUG] ${type}: ${message}`);
        return;
    }

    const logEntry = document.createElement('div');
    logEntry.className = 'debug-log';
    logEntry.innerHTML = `[${new Date().toLocaleTimeString()}] ${type.toUpperCase()}: ${message}`;

    const logContainer = debugPanel.querySelector('.debug-content');
    if (logContainer) {
        logContainer.appendChild(logEntry);
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    // Also log to console for backup
    console.log(`[DEBUG] ${type}: ${message}`);
};

// Theme toggle functionality with debug logging
window.initThemeToggle = function () {
    window.debugLog('initThemeToggle() called');

    const themeToggle = document.getElementById('theme-toggle');
    if (!themeToggle) {
        window.debugLog('Theme toggle button not found', 'error');
        return;
    }

    window.debugLog('Theme toggle button found', 'success');

    // Load saved theme or use system preference
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const currentTheme = savedTheme || (prefersDark ? 'dark' : 'light');

    window.debugLog(`System prefers dark: ${prefersDark}`);
    window.debugLog(`Saved theme: ${savedTheme}`);
    window.debugLog(`Current theme: ${currentTheme}`);

    document.documentElement.setAttribute('data-theme', currentTheme);
    window.debugLog(`Set data-theme to: ${currentTheme}`);

    window.updateToggleButton(currentTheme);

    themeToggle.onclick = function () {
        window.debugLog('Theme toggle clicked');

        const currentTheme = document.documentElement.getAttribute('data-theme');
        window.debugLog(`Current theme from data-theme: ${currentTheme}`);

        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        window.debugLog(`New theme will be: ${newTheme}`);

        document.documentElement.setAttribute('data-theme', newTheme);
        window.debugLog(`Set data-theme to: ${newTheme}`);

        localStorage.setItem('theme', newTheme);
        window.debugLog(`Saved theme to localStorage: ${newTheme}`);

        window.updateToggleButton(newTheme);
        window.debugLog(`Updated toggle button for: ${newTheme}`);
    };

    window.debugLog('Theme toggle initialized successfully');
};

window.updateToggleButton = function (theme) {
    const themeToggle = document.getElementById('theme-toggle');
    if (!themeToggle) {
        window.debugLog('Cannot update toggle button - not found', 'error');
        return;
    }

    const newText = theme === 'dark' ? '◑' : '◐';
    const newTitle = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';

    themeToggle.textContent = newText;
    themeToggle.title = newTitle;

    window.debugLog(`Updated button: text=${newText}, title=${newTitle}`);
};

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize the SPA on pages that opt-in
    if (document.querySelector('[data-init-app]')) {
        if (!window.__photorankApp) {
            window.__photorankApp = new PhotoRankApp();
        }
    }
    initThemeToggle();
});