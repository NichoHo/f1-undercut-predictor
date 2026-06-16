class F1UndercutApp {
    constructor() {
        this.currentYear = null;
        this.currentRound = null;
        this.currentLap = null;
        this.driverBehind = null;
        this.driverAhead = null;
        this.standings = [];
        this.maxLap = null;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.initChart();
    }
    
    initChart() {
        const ctx = document.getElementById('paceDeltaChart').getContext('2d');
        this.paceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['L-5', 'L-4', 'L-3', 'L-2', 'L-1'],
                datasets: [
                    {
                        label: 'Driver Ahead',
                        data: [0, 0, 0, 0, 0],
                        borderColor: '#ffffff',
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 0
                    },
                    {
                        label: 'Driver Behind',
                        data: [0, 0, 0, 0, 0],
                        borderColor: '#e10600', // Change this to F1 Red
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 3, // Slightly increased point radius makes it look sharper
                        pointBackgroundColor: '#e10600'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { display: false },
                    x: { 
                        grid: { display: false, drawBorder: false },
                        ticks: { color: '#888892', font: {family: 'monospace'} }
                    }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

    bindEvents() {
        // 1. Year selection
        document.getElementById('yearSelect').addEventListener('change', (e) => {
            this.currentYear = e.target.value;
            this.resetFormFrom('event');
            if (this.currentYear) {
                this.loadEvents(this.currentYear);
            }
        });
        
        // 2. Event selection
        document.getElementById('eventSelect').addEventListener('change', (e) => {
            this.currentRound = e.target.value;
            this.resetFormFrom('lap');
            if (this.currentYear && this.currentRound) {
                this.loadLaps(this.currentYear, this.currentRound);
            }
        });
        
        // 3. Lap Input (Trigger Standings fetch when valid)
        const lapInput = document.getElementById('lapInput');
        lapInput.addEventListener('change', (e) => {
            let val = parseInt(e.target.value);
            if (val >= 1 && val <= this.maxLap) {
                this.currentLap = val;
                this.loadStandings(this.currentYear, this.currentRound, this.currentLap);
            } else {
                this.showError(`Lap must be between 1 and ${this.maxLap}`);
            }
        });
        
        // 4. Driver Behind selection -> Auto-fill Driver Ahead
        document.getElementById('driverBehindSelect').addEventListener('change', (e) => {
            this.driverBehind = e.target.value;
            this.autoSelectDriverAhead();
            this.validateReadyState();
        });
        
        // 5. Predict Button
        document.getElementById('predictBtn').addEventListener('click', () => {
            this.predictUndercut();
        });

        // Modal Close logic
        document.getElementById('close-modal').addEventListener('click', () => {
            document.getElementById('timing-modal').classList.add('hidden');
        });
        document.querySelector('.modal-backdrop').addEventListener('click', () => {
            document.getElementById('timing-modal').classList.add('hidden');
        });

        // Best Timing Button
        document.getElementById('predictTimingBtn').addEventListener('click', () => {
            this.predictBestTiming();
        });
    }

    resetFormFrom(stage) {
        const eventSelect = document.getElementById('eventSelect');
        const lapInput = document.getElementById('lapInput');
        const driverBehindSelect = document.getElementById('driverBehindSelect');
        const driverAheadInput = document.getElementById('driverAheadInput');
        const predictBtn = document.getElementById('predictBtn');

        if (stage === 'event') {
            eventSelect.innerHTML = '<option value="" disabled selected>Select Race</option>';
            eventSelect.disabled = true;
            this.currentRound = null;
        }
        
        if (stage === 'event' || stage === 'lap') {
            lapInput.value = '';
            lapInput.disabled = true;
            document.getElementById('lap-help-text').classList.add('hidden');
            this.currentLap = null;
            this.maxLap = null;
        }

        driverBehindSelect.innerHTML = '<option value="" disabled selected>Select Driver</option>';
        driverBehindSelect.disabled = true;
        driverAheadInput.value = '';
        this.driverBehind = null;
        this.driverAhead = null;
        this.standings = [];
        predictBtn.disabled = true;
    }
    
    setLoadingState(elementId, isLoading, defaultText = '') {
        const el = document.getElementById(elementId);
        if (el.tagName === 'SELECT') {
            el.innerHTML = isLoading ? '<option value="">Loading...</option>' : `<option value="" disabled selected>${defaultText}</option>`;
            el.disabled = isLoading;
        }
    }
    
    async loadEvents(year) {
        try {
            this.setLoadingState('eventSelect', true);
            const response = await fetch(`/api/events/${year}`);
            const data = await response.json();
            
            const eventSelect = document.getElementById('eventSelect');
            this.setLoadingState('eventSelect', false, 'Select Race');
            
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
        } catch (error) {
            this.showError('Failed to load races');
        }
    }
    
    async loadLaps(year, round) {
        try {
            const lapInput = document.getElementById('lapInput');
            lapInput.disabled = true;
            
            const response = await fetch(`/api/laps/${year}/${round}`);
            const data = await response.json();
            
            if (data.laps && data.laps.length > 0) {
                const validLaps = data.laps.filter(lap => lap >= 1);
                if (validLaps.length > 0) {
                    this.maxLap = Math.max(...validLaps);
                    lapInput.max = this.maxLap;
                    lapInput.disabled = false;
                    
                    const helpText = document.getElementById('lap-help-text');
                    helpText.textContent = `Max Lap: ${this.maxLap}`;
                    helpText.classList.remove('hidden');
                } else {
                    this.showError('No valid lap data available');
                }
            }
        } catch (error) {
            this.showError('Failed to load lap data');
        }
    }
    
    async loadStandings(year, round, lap) {
        try {
            this.setLoadingState('driverBehindSelect', true);
            
            const response = await fetch(`/api/standings/${year}/${round}/${lap}`);
            const data = await response.json();
            
            this.standings = data.standings || [];
            this.populateDriverSelect();
        } catch (error) {
            this.showError('Failed to load driver standings');
        }
    }
    
    populateDriverSelect() {
        const select = document.getElementById('driverBehindSelect');
        this.setLoadingState('driverBehindSelect', false, 'Select Driver');
        
        if (!this.standings || this.standings.length === 0) {
            select.disabled = true;
            return;
        }
        
        // Sort by position just in case
        this.standings.sort((a, b) => a.position - b.position);

        this.standings.forEach(driver => {
            // Can't undercut if you are P1
            if (driver.position > 1) {
                const option = document.createElement('option');
                option.value = driver.driver;
                option.textContent = `${driver.driver} (P${driver.position}) - ${driver.compound || 'Unknown Tyres'}`;
                select.appendChild(option);
            }
        });
        
        select.disabled = false;
    }

    autoSelectDriverAhead() {
        const driverAheadInput = document.getElementById('driverAheadInput');
        
        if (!this.driverBehind) return;

        const behindData = this.standings.find(d => d.driver === this.driverBehind);
        
        if (behindData && behindData.position > 1) {
            const targetPosition = parseInt(behindData.position) - 1;
            const aheadData = this.standings.find(d => parseInt(d.position) === targetPosition);
            
            if (aheadData) {
                this.driverAhead = aheadData.driver;
                driverAheadInput.value = `${aheadData.driver} (P${aheadData.position})`;
                
                // Visual Flash
                driverAheadInput.classList.add("updated-flash");
                setTimeout(() => driverAheadInput.classList.remove("updated-flash"), 500);
            } else {
                this.driverAhead = null;
                driverAheadInput.value = "Target Unknown";
            }
        }
    }

    validateReadyState() {
        const isReady = (this.currentYear && this.currentRound && this.currentLap && this.driverBehind && this.driverAhead);
        document.getElementById('predictBtn').disabled = !isReady;
        document.getElementById('predictTimingBtn').disabled = !isReady;
    }
    
    async predictUndercut() {
        const predictBtn = document.getElementById('predictBtn');
        const btnText = predictBtn.querySelector(".btn-text");
        const btnLoader = predictBtn.querySelector(".btn-loader");
        const verdictOutput = document.getElementById("verdict-output");

        try {
            // UI Loading State
            predictBtn.classList.add("loading");
            btnText.classList.add("hidden");
            btnLoader.classList.remove("hidden");
            verdictOutput.textContent = "CALCULATING";
            verdictOutput.className = "verdict-text processing";

            const response = await fetch('/api/predict', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    year: this.currentYear,
                    round_num: this.currentRound,
                    lap_number: this.currentLap,
                    chaser: this.driverBehind, // Map to backend expecting 'chaser'
                    defender: this.driverAhead // Map to backend expecting 'defender'
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.updateDashboardUI(data);
            } else {
                this.showError(data.error || 'Prediction failed');
                verdictOutput.textContent = "ERROR";
                verdictOutput.className = "verdict-text danger";
            }
        } catch (error) {
            this.showError('Failed to get prediction', error);
        } finally {
            predictBtn.classList.remove("loading");
            btnText.classList.remove("hidden");
            btnLoader.classList.add("hidden");
        }
    }

    async predictBestTiming() {
        const timingBtn = document.getElementById('predictTimingBtn');
        const btnText = timingBtn.querySelector(".btn-text");
        const btnLoader = timingBtn.querySelector(".btn-loader");

        try {
            // UI Loading State
            timingBtn.classList.add("loading");
            btnText.classList.add("hidden");
            btnLoader.classList.remove("hidden");

            const response = await fetch('/api/best-timing', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    year: this.currentYear,
                    round_num: this.currentRound,
                    chaser: this.driverBehind,
                    defender: this.driverAhead
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.displayRecommendedLaps(data.recommended_laps || data.laps);
            } else {
                this.showError(data.error || 'Failed to analyze pit windows');
            }
        } catch (error) {
            this.showError('Failed to retrieve optimal timing', error);
        } finally {
            timingBtn.classList.remove("loading");
            btnText.classList.remove("hidden");
            btnLoader.classList.add("hidden");
        }
    }

    displayRecommendedLaps(laps) {
        const modal = document.getElementById('timing-modal');
        const list = document.getElementById('recommendedLapsList');
        
        if (!laps || laps.length === 0) {
            list.innerHTML = `<div class="system-label" style="text-align:center; padding: 2rem 0;">NO VIABLE WINDOWS FOUND</div>`;
            modal.classList.remove('hidden');
            return;
        }
        
        // Sort highest probability first
        laps.sort((a, b) => b.probability - a.probability);
        list.innerHTML = '';
        
        laps.forEach(lap => {
            const probPct = (lap.probability * 100).toFixed(1);
            const item = document.createElement('div');
            item.className = 'lap-item';
            item.innerHTML = `
                <div class="lap-details">
                    <div class="lap-number">TARGET LAP ${lap.lap}</div>
                    <div class="prob-container">
                        <div class="prob-track">
                            <div class="prob-fill" style="width: ${probPct}%"></div>
                        </div>
                        <div class="prob-text">${probPct}%</div>
                    </div>
                </div>
                <button class="select-lap-btn">SELECT <i class="fas fa-chevron-right"></i></button>
            `;
            
            item.addEventListener('click', () => {
                this.selectRecommendedLap(lap.lap);
            });
            
            list.appendChild(item);
        });
        
        modal.classList.remove('hidden');
    }

    selectRecommendedLap(lap) {
        // Close Modal
        document.getElementById('timing-modal').classList.add('hidden');
        
        // Update input and force a change event to reload standings
        const lapInput = document.getElementById('lapInput');
        lapInput.value = lap;
        
        // Dispatch 'change' event manually so your existing event listener catches it
        const event = new Event('change');
        lapInput.dispatchEvent(event);
    }

    updateDashboardUI(data) {
        const verdictOutput = document.getElementById("verdict-output");
        const confRing = document.getElementById("confidence-ring");
        const confPct = document.getElementById("confidence-percentage");
        const confBadge = document.getElementById("confidenceBadge");

        // Primary Verdict
        if (data.success) {
            verdictOutput.textContent = "VIABLE";
            verdictOutput.className = "verdict-text success";
        } else {
            verdictOutput.textContent = "RISK";
            verdictOutput.className = "verdict-text danger";
        }

        // Probability formatting
        const probVal = Math.round(data.probability * 100);
        confRing.setAttribute("stroke-dasharray", `${probVal}, 100`);
        this.animateValue(confPct, 0, probVal, 1000);
        confBadge.textContent = `${data.confidence} Confidence`;

        // Get local standings data for UI population
        const behindData = this.standings.find(d => d.driver === this.driverBehind);
        const aheadData = this.standings.find(d => d.driver === this.driverAhead);

        // Update the New Strategy Widget Cards
        document.getElementById("comp-name-ahead").textContent = this.driverAhead || "--";
        document.getElementById("comp-name-behind").textContent = this.driverBehind || "--";
        
        document.getElementById("comp-tire-ahead").textContent = aheadData ? (aheadData.compound || "UNK") : "UNK";
        document.getElementById("comp-tire-behind").textContent = behindData ? (behindData.compound || "UNK") : "UNK";

        // Inject calculated features if available
        if (data.features) {
            document.getElementById("comp-age-ahead").textContent = `${Math.round(data.features.Rival_Tyre_Age)} Laps`;
            
            // Dynamic Gap Trend Indicator based on Pace Delta
            const gapTrend = document.getElementById("gap-trend-display");
            if (gapTrend) {
                if (data.features.Pace_Delta < 0) {
                    gapTrend.innerHTML = '<i class="fas fa-arrow-down"></i> Closing';
                    gapTrend.style.background = 'rgba(0, 210, 190, 0.1)';
                    gapTrend.style.color = 'var(--accent-success)';
                } else {
                    gapTrend.innerHTML = '<i class="fas fa-arrow-up"></i> Losing Time';
                    gapTrend.style.background = 'rgba(225, 6, 0, 0.1)';
                    gapTrend.style.color = 'var(--accent-main)';
                }
            }
        }

        document.getElementById("current-gap-display").textContent = behindData ? behindData.gap : "--";

        // Update Chart (mocking pace traces until the API supplies actual lap arrays)
        this.paceChart.data.datasets[0].data = [84.2, 84.5, 84.3, 84.7, 85.0]; 
        this.paceChart.data.datasets[1].data = [84.8, 84.4, 84.1, 83.9, 83.6];
        this.paceChart.update();
    }
    
    animateValue(obj, start, end, duration) {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            obj.innerHTML = Math.floor(progress * (end - start) + start);
            if (progress < 1) window.requestAnimationFrame(step);
        };
        window.requestAnimationFrame(step);
    }

    showError(message, actualError = null) {
        // 1. Log the real JavaScript crash to the console
        if (actualError) {
            console.error("UI Rendering Crash Detail:", actualError);
        }
        
        // 2. Trigger the browser's built-in alert popup
        alert(`System Alert:\n${message}\n\nPlease press F12 to check the console for the exact error line.`);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new F1UndercutApp();
});