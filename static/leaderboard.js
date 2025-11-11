// API Configuration
const API_URL = '/api/leaderboard-data';
const REFRESH_INTERVAL = 2000; // 2 seconds

// State management
let currentTab = 'realtime';
let leaderboardData = null;
const pastelPalette = [
    '#FF9EB5', '#9CC7FF', '#FFBD8B', '#8EE3B3',
    '#B99CFF', '#FFC577', '#7FD7FF', '#FF9FD3',
    '#8DE58D', '#A9B6FF', '#FFB48F', '#7FE4D3',
    '#FFA4A4', '#8FD8FF', '#D49CFF', '#FFAD7A',
    '#7FE0A6', '#9FA8FF', '#FF9ECF', '#7FCBE4',
    '#C2FF7F', '#FFB1A8'
];
const teamColorMap = {};
let unusedColors = [...pastelPalette];

function assignColor(teamName) {
    if (teamColorMap[teamName]) return teamColorMap[teamName];
    if (unusedColors.length === 0) {
        unusedColors = [...pastelPalette].sort(() => Math.random() - 0.5);
    }
    const color = unusedColors.shift();
    teamColorMap[teamName] = color;
    return color;
}

/**
 * Switch between Real-time and Overall tabs
 */
function switchTab(tabName) {
    currentTab = tabName;
    
    // Update tab buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.tab === tabName) {
            btn.classList.add('active');
        }
    });
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-view`).classList.add('active');
    
    // Re-render current data
    if (leaderboardData) {
        if (tabName === 'realtime') {
            renderRealtimeView(leaderboardData);
        } else {
            renderOverallView(leaderboardData);
        }
    }
}

/**
 * Fetch leaderboard data from API
 */
async function fetchLeaderboard() {
    try {
        const response = await fetch(API_URL);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        leaderboardData = await response.json();
        updateLeaderboard(leaderboardData);
    } catch (error) {
        console.error('Failed to fetch leaderboard:', error);
        showError('Failed to load leaderboard data');
    }
}

/**
 * Update the leaderboard based on current tab
 */
function updateLeaderboard(data) {
    // Update active question indicator
    updateActiveQuestionIndicator(data.active_question_id);
    
    // Render based on current tab
    if (currentTab === 'realtime') {
        renderRealtimeView(data);
    } else {
        renderOverallView(data);
    }
}

/**
 * Update active question indicator in header
 */
function updateActiveQuestionIndicator(questionId) {
    const indicator = document.getElementById('active-question-indicator');
    if (questionId) {
        indicator.innerHTML = `<strong>Active:</strong> Question ${questionId}`;
        indicator.style.display = 'block';
    } else {
        indicator.innerHTML = '<strong>No active question</strong>';
        indicator.style.opacity = '0.5';
    }
}

/**
 * REAL-TIME VIEW: Grid layout with current question only
 */
function renderRealtimeView(data) {
    const grid = document.getElementById('realtime-grid');
    const activeQuestionId = data.active_question_id;
    
    if (!activeQuestionId) {
        grid.innerHTML = '<div class="loading-card">No active question. Waiting for admin to start...</div>';
        return;
    }
    
    // Split teams by real/fake for current question
    const realTeams = data.teams.filter(t => t.is_real && t.questions[activeQuestionId]);
    const fakeTeams = data.teams.filter(t => !t.is_real && t.questions[activeQuestionId]);

    const sortByScore = (list) => list.sort((a, b) => {
        const scoreA = a.questions[activeQuestionId]?.score || 0;
        const scoreB = b.questions[activeQuestionId]?.score || 0;
        return scoreB - scoreA;
    });

    sortByScore(realTeams);
    sortByScore(fakeTeams);

    let cardsHTML = '';
    realTeams.forEach(team => {
        cardsHTML += createTeamCard(team, activeQuestionId, true);
    });
    fakeTeams.forEach(team => {
        cardsHTML += createTeamCard(team, activeQuestionId, false);
    });
    
    grid.innerHTML = cardsHTML || '<div class="loading-card">Loading teams...</div>';
}

/**
 * Create a team card for grid view
 */
function createTeamCard(team, questionId, isReal) {
    const questionData = team.questions[questionId];
    
    // Default values
    let score = 0;
    let correctCount = 0;
    let wrongCount = 0;
    
    if (questionData) {
        score = questionData.score || 0;
        correctCount = questionData.correct_count || 0;
        wrongCount = questionData.wrong_count || 0;
    }
    
    // Determine color: green if has score, red if no score
    const scoreClass = score > 0 ? 'score-green' : 'score-red';
    const cardColor = assignColor(team.team_name);
    
    return `
        <div class="team-card ${isReal ? 'real-team' : ''}" style="--team-color: ${cardColor};">
            <div class="team-body">
                <div class="team-name">${team.team_name}</div>
                <div class="score-panel">
                    <span class="score-label">Score</span>
                    <span class="score-number ${scoreClass}">${score.toFixed(1)}</span>
                </div>
            </div>
            <div class="team-status">
                <div class="status-box correct">
                    ${correctCount}
                    <span>correct</span>
                </div>
                <div class="status-box wrong">
                    ${wrongCount}
                    <span>wrong</span>
                </div>
            </div>
        </div>
    `;
}

/**
 * OVERALL VIEW: Table with all questions and ranking
 */
function renderOverallView(data) {
    // Update question headers
    updateQuestionHeaders(data.questions);
    
    // Sort teams by total score (descending)
    const sortedTeams = [...data.teams].sort((a, b) => b.total_score - a.total_score);
    
    // Build table rows
    const tbody = document.getElementById('overall-body');
    let rowsHTML = '';
    
    sortedTeams.forEach((team, index) => {
        const rank = index + 1;
        const isRealTeam = team.is_real;
        rowsHTML += createTeamRow(team, rank, data.questions, isRealTeam);
    });
    
    // Total columns: Rank(1) + Team(1) + Questions(N) + Total(1) = N+3
    const totalCols = data.questions.length + 3;
    tbody.innerHTML = rowsHTML || `<tr><td colspan="${totalCols}" class="loading">No data</td></tr>`;
}

/**
 * Update question headers in overall table
 */
function updateQuestionHeaders(questions) {
    // Update colspan for "QUESTIONS" header
    const questionsHeader = document.querySelector('.questions-header');
    if (questionsHeader) {
        questionsHeader.setAttribute('colspan', questions.length);
    }
    
    // Update question column headers (Q1, Q2, Q3, ...)
    const headerRow = document.getElementById('overall-question-headers');
    headerRow.innerHTML = questions.map(q => `<th class="question-col">Q${q}</th>`).join('');
}

/**
 * Create a team row for overall table
 */
function createTeamRow(team, rank, questions, isRealTeam) {
    const rankBadge = rank;  // Simple number, no medals
    const teamClass = isRealTeam ? 'real-team-row' : '';
    const teamDisplay = team.team_name;  // No star icon
    
    // Build question cells
    let questionCells = '';
    questions.forEach(qId => {
        const qData = team.questions[qId];
        if (qData) {
            const submissions = renderSubmissions(qData.correct_count, qData.wrong_count);
            const scoreClass = qData.score > 0 ? 'score-green' : 'score-red';
            questionCells += `
                <td class="question-cell">
                    <div class="submissions">${submissions}</div>
                    <div class="score-value ${scoreClass}">${qData.score.toFixed(1)}</div>
                </td>
            `;
        } else {
            questionCells += `<td class="question-cell">-</td>`;
        }
    });
    
    const totalScoreClass = team.total_score > 0 ? 'score-green' : 'score-red';
    
    return `
        <tr class="${teamClass}">
            <td>${rankBadge}</td>
            <td style="text-align: left;">${teamDisplay}</td>
            ${questionCells}
            <td class="score-value ${totalScoreClass}">${team.total_score.toFixed(1)}</td>
        </tr>
    `;
}

/**
 * Render submission counts (simple text, no icons)
 */
function renderSubmissions(correctCount, wrongCount) {
    if (correctCount === 0 && wrongCount === 0) return '-';
    return `<span class="correct-count">${correctCount}</span> / <span class="wrong-count">${wrongCount}</span>`;
}

/**
 * Show error message
 */
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    errorDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #ff3333;
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        z-index: 1000;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    `;
    document.body.appendChild(errorDiv);
    
    setTimeout(() => errorDiv.remove(), 5000);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('🏆 Leaderboard initialized');
    
    // Initial fetch
    fetchLeaderboard();
    
    // Set up auto-refresh
    setInterval(fetchLeaderboard, REFRESH_INTERVAL);
    
    // Log refresh activity
    console.log(`🔄 Auto-refresh enabled (every ${REFRESH_INTERVAL/1000}s)`);
});

// Refresh when tab becomes visible
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        console.log('▶️ Tab visible - refreshing');
        fetchLeaderboard();
    }
});

// Expose switchTab to global scope for onclick handlers
window.switchTab = switchTab;
