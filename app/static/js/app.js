// Ultra-minimalist PhotoRank app

class PhotoRankApp {
    constructor() {
        this.ws = null;
        this.currentPair = null;
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
                if (this._keyboardVotingLocked) return;
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
            
            const response = await this.makeAuthenticatedRequest('/api/photos/pair/session', {
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
                data.next_milestone,
                data.match_importance,
                data.photo_ranks
            );
        }
    }
    
    updateProgressDisplay(progressText, progressPercentage, nextMilestone, matchImportance, photoRanks) {
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

        // Build progress text with milestone anticipation
        let displayText = `Progress: ${progressText} pairs voted`;
        if (nextMilestone) {
            const untilTop5 = nextMilestone.pairs_until_top5;
            const untilTop10 = nextMilestone.pairs_until_top10;

            if (untilTop5 && untilTop5 > 0) {
                displayText += ` • NEXT TOP 5 IN ${untilTop5} PAIRS`;
            }
            if (untilTop10 && untilTop10 > 0 && (!untilTop5 || untilTop10 < untilTop5)) {
                displayText += ` • NEXT TOP 10 IN ${untilTop10} PAIRS`;
            }
        }

        // Add current match importance
        if (matchImportance) {
            displayText += ` • ${matchImportance} MATCH!`;
        }

        if (progressText && progressPercentage !== undefined) {
            progressContainer.innerHTML = `
                <div class="progress-text">${displayText}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${progressPercentage}%;"></div>
                </div>
                <div class="progress-text" style="margin-top: 0.25rem; font-size: 0.8rem;">${progressPercentage.toFixed(1)}% complete</div>
            `;
        } else {
            progressContainer.innerHTML = '';
        }

        // Handle important match UI
        this.updateImportantMatchUI(matchImportance, photoRanks);
    }

    updateImportantMatchUI(matchImportance, photoRanks) {
        // Remove existing important match UI
        const existingUI = document.querySelector('.important-match-ui');
        if (existingUI) {
            existingUI.remove();
        }

        if (matchImportance && photoRanks && photoRanks.length === 2) {
            // Create important match indicator
            const matchUI = document.createElement('div');
            matchUI.className = 'important-match-ui';

            if (matchImportance === 'TOP_5') {
                matchUI.innerHTML = `
                    <div style="text-align: center; margin: 1rem 0; font-weight: bold; font-size: 1.1rem;">
                        ${matchImportance} MATCHUP
                    </div>
                    <div style="text-align: center; margin-bottom: 1rem; color: var(--secondary-text);">
                        Rank #${photoRanks[0]} vs Rank #${photoRanks[1]}
                    </div>
                `;
            } else if (matchImportance === 'TOP_10') {
                matchUI.innerHTML = `
                    <div style="text-align: center; margin: 1rem 0; font-weight: bold;">
                        ${matchImportance} MATCHUP
                    </div>
                    <div style="text-align: center; margin-bottom: 1rem; color: var(--secondary-text);">
                        Rank #${photoRanks[0]} vs Rank #${photoRanks[1]}
                    </div>
                `;
            }

            // Insert before the photo pair
            const photoPair = document.querySelector('.photo-pair');
            if (photoPair && photoPair.parentNode) {
                photoPair.parentNode.insertBefore(matchUI, photoPair);
            }
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
        
        if (!this.isAuthenticated()) {
            window.location.href = '/login';
            return;
        }
        
        const clickedContainer = event.currentTarget;
        const isFirst = clickedContainer.id === 'photo1';
        
        const winner = isFirst ? this.currentPair[0] : this.currentPair[1];
        const loser = isFirst ? this.currentPair[1] : this.currentPair[0];
        
        try {
            await this.makeAuthenticatedRequest('/api/votes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    winner_id: winner.id,
                    loser_id: loser.id
                })
            });
            
            // Fade out loser
            const loserContainer = isFirst ? 
                document.getElementById('photo2') : 
                document.getElementById('photo1');
            
            loserContainer.style.opacity = '0.3';
            
            setTimeout(() => {
                this.loadPhotoPair();
            }, 250);
            
        } catch (error) {
            if (error.message !== 'Authentication required') {
                console.error('Error submitting vote:', error);
            }
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
        }).catch(() => {});

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
window.debugLog = function(message, type = 'info') {
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
window.initThemeToggle = function() {
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

    themeToggle.onclick = function() {
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

window.updateToggleButton = function(theme) {
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