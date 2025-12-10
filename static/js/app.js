class F1UndercutApp {
    constructor() {
        this.currentYear = null;
        this.currentRound = null;
        this.currentLap = null;
        this.chaserDriver = null;
        this.defenderDriver = null;
        this.standings = [];
        
        this.init();
    }
    
    init() {
        this.bindEvents();
    }
    
    bindEvents() {
        // Year selection
        document.getElementById('yearSelect').addEventListener('change', (e) => {
            this.currentYear = e.target.value;
            if (this.currentYear) {
                this.loadEvents(this.currentYear);
            }
        });
        
        // Event selection
        document.getElementById('eventSelect').addEventListener('change', (e) => {
            this.currentRound = e.target.value;
            if (this.currentYear && this.currentRound) {
                this.loadLaps(this.currentYear, this.currentRound);
            }
        });
        
        // Lap slider
        document.getElementById('lapSlider').addEventListener('input', (e) => {
            this.currentLap = parseInt(e.target.value);
            document.getElementById('lapValue').textContent = this.currentLap;
            document.getElementById('currentLapDisplay').textContent = this.currentLap;
            
            if (this.currentYear && this.currentRound && this.currentLap) {
                this.loadStandings(this.currentYear, this.currentRound, this.currentLap);
            }
        });
        
        // Driver selection
        document.getElementById('chaserSelect').addEventListener('change', (e) => {
            this.chaserDriver = e.target.value;
            this.updateSelectedDrivers();
        });
        
        document.getElementById('defenderSelect').addEventListener('change', (e) => {
            this.defenderDriver = e.target.value;
            this.updateSelectedDrivers();
        });
        
        // Predict button
        document.getElementById('predictBtn').addEventListener('click', () => {
            this.predictUndercut();
        });
    }
    
    showLoadingInSelect(selectId) {
        const select = document.getElementById(selectId);
        select.innerHTML = '<option value="">Loading...</option>';
        select.disabled = true;
    }
    
    showLoadingInPanel(panelId) {
        const panel = document.getElementById(panelId);
        
        // Clear existing content
        panel.innerHTML = '';
        
        panel.classList.add('loading-overlay');
        
        const spinner = document.createElement('div');
        spinner.className = 'loading-spinner';
        spinner.innerHTML = '<div class="spinner"></div>';
        panel.appendChild(spinner);
    }
    
    hideLoadingInPanel(panelId) {
        const panel = document.getElementById(panelId);
        panel.classList.remove('loading-overlay');
        
        const spinner = panel.querySelector('.loading-spinner');
        if (spinner) {
            spinner.remove();
        }
    }
    
    async loadEvents(year) {
        try {
            console.log(`Loading events for ${year}...`);
            this.showLoadingInSelect('eventSelect');
            
            const response = await fetch(`/api/events/${year}`);
            const data = await response.json();
            
            const eventSelect = document.getElementById('eventSelect');
            eventSelect.innerHTML = '<option value="">Select Race</option>';
            
            if (data.events && data.events.length > 0) {
                data.events.forEach(event => {
                    const option = document.createElement('option');
                    option.value = event.RoundNumber;
                    option.textContent = `${event.RoundNumber}. ${event.EventName}`;
                    eventSelect.appendChild(option);
                });
                eventSelect.disabled = false;
            } else {
                this.showError('No races found for this year');
            }
            
            this.clearSelections();
        } catch (error) {
            console.error('Error loading events:', error);
            this.showError('Failed to load races');
        }
    }
    
    async loadLaps(year, round) {
        try {
            console.log(`Loading laps for ${year} Round ${round}...`);
            this.showLoadingInPanel('standingsList');
            
            const response = await fetch(`/api/laps/${year}/${round}`);
            const data = await response.json();
            
            this.hideLoadingInPanel('standingsList');
            
            if (data.laps && data.laps.length > 0) {
                const slider = document.getElementById('lapSlider');
                
                // Filter laps to only include laps >= 1
                const validLaps = data.laps.filter(lap => lap >= 1);
                
                if (validLaps.length > 0) {
                    // Always start at lap 1, or the minimum lap that's at least 1
                    const minLap = Math.max(1, Math.min(...validLaps));
                    const maxLap = Math.max(...validLaps);
                    
                    slider.min = minLap;
                    slider.max = maxLap;
                    slider.value = minLap;  // This will be 1 or the smallest lap >= 1
                    slider.disabled = false;
                    
                    this.currentLap = parseInt(slider.value);
                    document.getElementById('lapValue').textContent = this.currentLap;
                    document.getElementById('currentLapDisplay').textContent = this.currentLap;
                    
                    this.loadStandings(year, round, this.currentLap);
                } else {
                    this.showError('No valid lap data available (all laps are below 1)');
                }
            } else {
                this.showError('No pit stop data available for this race');
            }
        } catch (error) {
            console.error('Error loading laps:', error);
            this.hideLoadingInPanel('standingsList');
            this.showError('Failed to load lap data');
        }
    }
    
    async loadStandings(year, round, lap) {
        try {
            console.log(`Loading standings for ${year} Round ${round} Lap ${lap}...`);
            this.showLoadingInPanel('standingsList');
            
            const response = await fetch(`/api/standings/${year}/${round}/${lap}`);
            const data = await response.json();
            
            this.hideLoadingInPanel('standingsList');
            
            this.standings = data.standings || [];
            this.updateStandingsList();
            this.updateDriverSelects();
        } catch (error) {
            console.error('Error loading standings:', error);
            this.hideLoadingInPanel('standingsList');
            this.showError('Failed to load driver standings');
        }
    }
    
    updateStandingsList() {
        const standingsList = document.getElementById('standingsList');
        
        if (!this.standings || this.standings.length === 0) {
            standingsList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>No standings data available</p>
                </div>
            `;
            return;
        }
        
        standingsList.innerHTML = '';
        
        this.standings.forEach(driver => {
            const item = document.createElement('div');
            item.className = 'standing-item';
            
            if (driver.driver === this.chaserDriver || driver.driver === this.defenderDriver) {
                item.classList.add('selected');
            }
            
            item.innerHTML = `
                <div class="position">${driver.position}</div>
                <div class="driver-info">
                    <div class="driver-code">${driver.driver}</div>
                    <div class="driver-team">${driver.team}</div>
                </div>
                <div class="tyre-compound tyre-${driver.compound}">${driver.compound}</div>
            `;
            
            item.addEventListener('click', () => {
                this.selectDriver(driver.driver);
            });
            
            standingsList.appendChild(item);
        });
    }
    
    updateDriverSelects() {
        const chaserSelect = document.getElementById('chaserSelect');
        const defenderSelect = document.getElementById('defenderSelect');
        
        chaserSelect.innerHTML = '<option value="">Select Chaser</option>';
        defenderSelect.innerHTML = '<option value="">Select Defender</option>';
        
        if (!this.standings || this.standings.length === 0) {
            chaserSelect.disabled = true;
            defenderSelect.disabled = true;
            return;
        }
        
        this.standings.forEach(driver => {
            const option = document.createElement('option');
            option.value = driver.driver;
            option.textContent = `${driver.driver} (P${driver.position})`;
            
            chaserSelect.appendChild(option.cloneNode(true));
            defenderSelect.appendChild(option.cloneNode(true));
        });
        
        chaserSelect.disabled = false;
        defenderSelect.disabled = false;
        
        if (this.chaserDriver) chaserSelect.value = this.chaserDriver;
        if (this.defenderDriver) defenderSelect.value = this.defenderDriver;
    }
    
    selectDriver(driver) {
        if (!this.chaserDriver) {
            this.chaserDriver = driver;
            document.getElementById('chaserSelect').value = driver;
        } else if (!this.defenderDriver) {
            this.defenderDriver = driver;
            document.getElementById('defenderSelect').value = driver;
        } else {
            this.defenderDriver = driver;
            document.getElementById('defenderSelect').value = driver;
        }
        
        this.updateSelectedDrivers();
    }
    
    updateSelectedDrivers() {
        this.updateStandingsList();
        
        const predictBtn = document.getElementById('predictBtn');
        predictBtn.disabled = !(this.chaserDriver && this.defenderDriver);
        
        document.getElementById('chaserBox').classList.toggle('active', this.chaserDriver !== null);
        document.getElementById('defenderBox').classList.toggle('active', this.defenderDriver !== null);
    }
    
    async predictUndercut() {
        if (!this.validateSelection()) return;
        
        try {
            this.showLoading();
            const response = await fetch('/api/predict', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    year: this.currentYear,
                    round_num: this.currentRound,
                    lap_number: this.currentLap,
                    chaser: this.chaserDriver,
                    defender: this.defenderDriver
                })
            });
            
            const data = await response.json();
            this.hideLoading();
            
            if (response.ok) {
                this.displayPrediction(data);
            } else {
                this.showError(data.error || 'Prediction failed');
            }
        } catch (error) {
            console.error('Error predicting undercut:', error);
            this.hideLoading();
            this.showError('Failed to get prediction');
        }
    }
    
    displayPrediction(data) {
        document.getElementById('predictionResult').style.display = 'block';
        document.getElementById('successBadge').textContent = data.success ? 'SUCCESS' : 'FAIL';
        document.getElementById('successBadge').className = `success-badge ${data.success ? 'success' : 'fail'}`;
        document.getElementById('probabilityValue').textContent = `${(data.probability * 100).toFixed(1)}%`;
        document.getElementById('confidenceBadge').textContent = `${data.confidence} Confidence`;
    }
    
    validateSelection() {
        if (!this.currentYear || !this.currentRound || !this.currentLap) {
            this.showError('Please select year, race, and lap');
            return false;
        }
        
        if (!this.chaserDriver || !this.defenderDriver) {
            this.showError('Please select both chaser and defender drivers');
            return false;
        }
        
        if (this.chaserDriver === this.defenderDriver) {
            this.showError('Chaser and defender must be different drivers');
            return false;
        }
        
        return true;
    }
    
    clearSelections() {
        this.currentLap = null;
        this.chaserDriver = null;
        this.defenderDriver = null;
        
        document.getElementById('lapSlider').value = 1;
        document.getElementById('lapSlider').disabled = true;
        document.getElementById('lapValue').textContent = '1';
        document.getElementById('currentLapDisplay').textContent = '1';
        document.getElementById('chaserSelect').value = '';
        document.getElementById('defenderSelect').value = '';
        document.getElementById('chaserSelect').disabled = true;
        document.getElementById('defenderSelect').disabled = true;
        document.getElementById('predictionResult').style.display = 'none';
        
        document.getElementById('standingsList').innerHTML = `
            <div class="empty-state">
                <i class="fas fa-flag-checkered"></i>
                <p>Select a race and lap to see standings</p>
            </div>
        `;
    }
    
    showLoading() {
        const predictBtn = document.getElementById('predictBtn');
        predictBtn.classList.add('loading');
        predictBtn.disabled = true;
        predictBtn.innerHTML = '<div class="spinner"></div>';
    }
    
    hideLoading() {
        const predictBtn = document.getElementById('predictBtn');
        predictBtn.classList.remove('loading');
        predictBtn.disabled = false;
        predictBtn.textContent = 'Predict Undercut';
    }
    
    showError(message) {
        // Remove existing error messages
        const existingErrors = document.querySelectorAll('.error-message');
        existingErrors.forEach(error => error.remove());
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
        
        // Insert at top of middle panel
        const middlePanel = document.querySelector('.middle-panel');
        if (middlePanel) {
            middlePanel.insertBefore(errorDiv, middlePanel.firstChild);
        }
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 5000);
    }
}

// Initialize app when page loads
document.addEventListener('DOMContentLoaded', () => {
    new F1UndercutApp();
});