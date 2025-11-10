// Admin Dashboard JavaScript
const REFRESH_INTERVAL = 2000; // 2 seconds
const COUNTDOWN_INTERVAL = 1000; // 1 second for smooth countdown

// API Endpoints
const API = {
    START_QUESTION: '/admin/start-question',
    STOP_QUESTION: '/admin/stop-question',
    RESET_ALL: '/admin/reset',
    SESSIONS: '/admin/sessions',
    CONFIG: '/config'
};

let activeQuestionId = null;
let questionConfig = {};
let countdownTimer = null;
let remainingSeconds = 0;

/**
 * Initialize dashboard
 */
document.addEventListener('DOMContentLoaded', () => {
    log('Admin dashboard initialized', 'info');
    
    // Load question config
    loadQuestionConfig();
    
    // Initial status fetch
    refreshStatus();
    refreshSessions();
    
    // Auto-refresh (data from server every 2s)
    setInterval(() => {
        refreshStatus();
        refreshSessions();
    }, REFRESH_INTERVAL);
    
    // Smooth countdown (every 1s)
    startCountdownTimer();
    
    // Setup question ID input listener
    document.getElementById('question-id').addEventListener('input', updateQuestionInfo);
});

/**
 * Start smooth countdown timer
 */
function startCountdownTimer() {
    if (countdownTimer) {
        clearInterval(countdownTimer);
    }
    
    countdownTimer = setInterval(() => {
        if (remainingSeconds > 0) {
            remainingSeconds--;
            updateCountdownDisplay();
        }
    }, COUNTDOWN_INTERVAL);
}

/**
 * Load question configuration from server
 */
async function loadQuestionConfig() {
    try {
        const response = await fetch(API.CONFIG);
        const data = await response.json();
        questionConfig = data.questions || {};
        log(`Loaded ${Object.keys(questionConfig).length} questions from config`, 'success');
    } catch (error) {
        log('Failed to load question config', 'error');
        console.error(error);
    }
}

/**
 * Update question info display when question ID changes
 */
function updateQuestionInfo() {
    const qId = document.getElementById('question-id').value;
    const infoDiv = document.getElementById('question-info');
    
    if (!qId || !questionConfig[qId]) {
        infoDiv.classList.add('hidden');
        return;
    }
    
    const q = questionConfig[qId];
    infoDiv.classList.remove('hidden');
    infoDiv.innerHTML = `
        <strong>Question ${qId}</strong><br>
        Type: <span style="color: var(--color-success)">${q.type}</span><br>
        Scene: ${q.scene_id} | Video: ${q.video_id}<br>
        Events: ${q.num_events || 0}<br>
        <hr style="margin: 10px 0; border-color: var(--border-color);">
        Time Limit: <strong>${q.default_time_limit}s</strong> (+ ${q.default_buffer_time}s buffer)
    `;
}

/**
 * Start a question
 */
async function startQuestion() {
    const questionId = parseInt(document.getElementById('question-id').value);
    const timeLimit = parseInt(document.getElementById('time-limit').value) || 300;
    const bufferTime = parseInt(document.getElementById('buffer-time').value) || 10;
    
    // Validate question ID exists in loaded config
    if (!questionId || !questionConfig[questionId]) {
        const maxQ = Math.max(...Object.keys(questionConfig).map(Number));
        log(`Invalid question ID. Available: 1-${maxQ}`, 'error');
        return;
    }
    
    try {
        const response = await fetch(API.START_QUESTION, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question_id: questionId,
                time_limit: timeLimit,
                buffer_time: bufferTime
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            log(`Started Question ${questionId} (${timeLimit}s + ${bufferTime}s buffer)`, 'success');
            activeQuestionId = questionId;
            refreshStatus();
            refreshSessions();
        } else {
            log(`Failed to start question: ${data.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        log(`Error starting question: ${error.message}`, 'error');
        console.error(error);
    }
}

/**
 * Quick start question with default settings
 */
function startQuestionQuick(questionId) {
    document.getElementById('question-id').value = questionId;
    updateQuestionInfo();
    startQuestion();
}

/**
 * Stop the currently active question
 */
async function stopCurrentQuestion() {
    const questionId = parseInt(document.getElementById('question-id').value);
    
    if (!questionId) {
        log('Please enter a question ID to stop', 'error');
        return;
    }
    
    try {
        const response = await fetch(API.STOP_QUESTION, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question_id: questionId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            log(`Stopped Question ${questionId}`, 'warning');
            if (activeQuestionId === questionId) {
                activeQuestionId = null;
            }
            refreshStatus();
            refreshSessions();
        } else {
            log(`Failed to stop question: ${data.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        log(`Error stopping question: ${error.message}`, 'error');
        console.error(error);
    }
}

/**
 * Reset all sessions
 */
async function resetAll() {
    if (!confirm('⚠️ Are you sure you want to reset ALL sessions? This cannot be undone!')) {
        return;
    }
    
    try {
        const response = await fetch(API.RESET_ALL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            log('🔄 All sessions reset successfully', 'warning');
            activeQuestionId = null;
            refreshStatus();
            refreshSessions();
        } else {
            log(`❌ Failed to reset: ${data.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        log(`❌ Error resetting: ${error.message}`, 'error');
        console.error(error);
    }
}

/**
 * Refresh status panel
 */
async function refreshStatus() {
    try {
        // Get all sessions
        const response = await fetch(API.SESSIONS);
        const data = await response.json();
        
        console.log('Sessions data:', data); // Debug log
        
        // Find active session
        const activeSessions = data.sessions?.filter(s => s.is_active) || [];
        
        console.log('Active sessions:', activeSessions); // Debug log
        
        if (activeSessions.length === 0) {
            // No active question
            document.getElementById('active-question').textContent = 'None';
            document.getElementById('active-question').classList.add('inactive');
            document.getElementById('time-remaining').textContent = '-';
            document.getElementById('time-remaining').classList.add('inactive');
            document.getElementById('teams-submitted').textContent = '0';
            document.getElementById('teams-completed').textContent = '0';
            activeQuestionId = null;
            remainingSeconds = 0;
            return;
        }
        
        // Get the most recent active session (should be only one)
        const session = activeSessions[activeSessions.length - 1];
        activeQuestionId = session.question_id;
        
        console.log('Active session:', session); // Debug log
        
        // Update status display
        document.getElementById('active-question').textContent = `Question ${session.question_id}`;
        document.getElementById('active-question').classList.remove('inactive');
        
        // Calculate remaining time
        const elapsed = session.elapsed_time || 0;
        const totalTime = (session.time_limit || 300) + (session.buffer_time || 10);
        remainingSeconds = Math.max(0, Math.floor(totalTime - elapsed));
        
        console.log('Remaining seconds:', remainingSeconds); // Debug log
        
        updateCountdownDisplay();
        document.getElementById('time-remaining').classList.remove('inactive');
        
        document.getElementById('teams-submitted').textContent = session.total_submissions || 0;
        document.getElementById('teams-completed').textContent = session.completed_teams || 0;
        
    } catch (error) {
        console.error('Error refreshing status:', error);
        // Reset to no active question on error
        document.getElementById('active-question').textContent = 'None';
        document.getElementById('active-question').classList.add('inactive');
        document.getElementById('time-remaining').textContent = '-';
        document.getElementById('time-remaining').classList.add('inactive');
        activeQuestionId = null;
        remainingSeconds = 0;
    }
}

/**
 * Update countdown display (called every second)
 */
function updateCountdownDisplay() {
    const minutes = Math.floor(remainingSeconds / 60);
    const seconds = remainingSeconds % 60;
    document.getElementById('time-remaining').textContent = 
        `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

/**
 * Refresh sessions table
 */
async function refreshSessions() {
    try {
        const response = await fetch(API.SESSIONS);
        const data = await response.json();
        
        const tbody = document.getElementById('sessions-tbody');
        
        if (!data.sessions || data.sessions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading">No sessions yet</td></tr>';
            return;
        }
        
        let html = '';
        data.sessions.forEach(session => {
            const statusBadge = session.is_active 
                ? '<span class="status-badge status-active">Active</span>'
                : '<span class="status-badge status-inactive">Stopped</span>';
            
            html += `
                <tr>
                    <td><strong>Q${session.question_id}</strong></td>
                    <td>${questionConfig[session.question_id]?.type || '-'}</td>
                    <td>${statusBadge}</td>
                    <td>${session.time_limit}s (+${session.buffer_time}s)</td>
                    <td>${session.total_submissions}</td>
                    <td>${session.completed_teams}</td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;
    } catch (error) {
        console.error('Error refreshing sessions:', error);
    }
}

/**
 * Add log entry
 */
function log(message, type = 'info') {
    const logContainer = document.getElementById('log-container');
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    
    const now = new Date();
    const time = now.toLocaleTimeString();
    
    entry.innerHTML = `
        <span class="log-time">[${time}]</span>
        ${message}
    `;
    
    // Insert at top
    logContainer.insertBefore(entry, logContainer.firstChild);
    
    // Limit log entries
    const entries = logContainer.querySelectorAll('.log-entry');
    if (entries.length > 50) {
        entries[entries.length - 1].remove();
    }
    
    console.log(`[${type.toUpperCase()}] ${message}`);
}

// Expose functions to global scope
window.startQuestion = startQuestion;
window.startQuestionQuick = startQuestionQuick;
window.stopQuestion = stopQuestion;
window.resetAll = resetAll;
