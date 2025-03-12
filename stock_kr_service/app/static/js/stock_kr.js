document.addEventListener('DOMContentLoaded', async function () {
    const loader = document.getElementById('loader');
    const stockTable = document.getElementById('stock-table');

    // Config 값을 JavaScript 변수로 전달
    const { 
        AUTH_SERVICE_URL, 
        EXCHANGE_SERVICE_URL, 
        PORTFOLIO_SERVICE_URL 
    } = window.CONFIG || {};  // CONFIG가 undefined일 경우 빈 객체로 처리

    if (!AUTH_SERVICE_URL || !EXCHANGE_SERVICE_URL || !PORTFOLIO_SERVICE_URL) {
        console.error("Config 값이 정의되지 않았습니다.");
        return;
    }

    // 로그인 상태 확인 함수
    async function checkLoginStatus() {
        try {
            // ✅ Auth-Service의 API 호출 (Config 사용)
            const response = await fetch(`${AUTH_SERVICE_URL}/check-login`, { 
                credentials: 'include'  // 쿠키 전송 필수
            });
            const data = await response.json();
            const navbarRight = document.querySelector('nav.navbar-right');
    
            if (data.loggedIn && data.userData) {
                navbarRight.innerHTML = `
                    <a class="button" href="${EXCHANGE_SERVICE_URL}">환전하기</a>
                    <a class="button" href="${PORTFOLIO_SERVICE_URL}">마이페이지</a>
                    <span>${data.userData.username}</span>
                    <a class="button" id="logout-button" href="#">로그아웃</a>
                `;
    
                document.getElementById('logout-button').addEventListener('click', async function (event) {
                    event.preventDefault();
                    // ✅ Auth-Service의 logout 호출
                    await fetch(`${AUTH_SERVICE_URL}/logout`, { method: 'GET', mode: 'no-cors' });
                    alert('로그아웃되었습니다!');
                    window.location.reload();
                });
            } else {
                navbarRight.innerHTML = `
                    <a class="button" href="${EXCHANGE_SERVICE_URL}">환전하기</a>
                    <a class="button" href="${PORTFOLIO_SERVICE_URL}">마이페이지</a>
                    <a class="button" href="${AUTH_SERVICE_URL}/login">로그인</a>
                `;
            }
        } catch (error) {
            console.error('로그인 상태 확인 실패:', error);
        }
    }    
    

    // 주식 데이터 불러오기 (초기)
    async function fetchInitialStockData() {
        loader.style.display = 'block';
        stockTable.style.display = 'none';
        try {
            const response = await fetch('/api/realtime-stock-data');
            if (!response.ok) throw new Error('Network response was not ok');
            const data = await response.json();
            updateStockList(data);
        } catch (error) {
            showError('초기 주식 데이터를 가져오는 중 오류가 발생했습니다');
            console.error('Error fetching initial stock data:', error);
        } finally {
            loader.style.display = 'none';
            stockTable.style.display = 'table';
        }
    }

    // 실시간 주식 데이터 갱신
    async function fetchRealTimeStockData() {
        try {
            const response = await fetch('/api/realtime-stock-data');
            if (!response.ok) throw new Error('Network response was not ok');
            const data = await response.json();
            updateStockList(data);
        } catch (error) {
            showError('실시간 주식 데이터를 가져오는 중 오류가 발생했습니다');
            console.error('Error fetching real-time stock data:', error);
        }
    }

    // 주식 목록 업데이트
    function updateStockList(data) {
        const tbody = document.getElementById('stock-data');
        const errorDiv = document.getElementById('error-message');

        tbody.innerHTML = '';
        errorDiv.style.display = 'none';

        if (data.error) {
            showError(data.error);
            return;
        }

        data.forEach(stock => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="text-left"><a href="#" class="stock-link" data-code="${stock.code}">${stock.name || 'N/A'}</a></td>
                <td class="text-right ${stock.change > 0 ? 'change-positive' : stock.change < 0 ? 'change-negative' : 'change-0'}">
                    ${stock.price.toLocaleString()}원
                </td>
                <td class="text-right">${stock.open.toLocaleString()}원</td>
                <td class="text-right">${stock.high.toLocaleString()}원</td>
                <td class="text-right">${stock.low.toLocaleString()}원</td>
                <td class="text-right ${stock.change > 0 ? 'change-positive' : stock.change < 0 ? 'change-negative' : 'change-0'}">
                    ${stock.change !== 0 ? stock.change.toLocaleString() + '원' : '0원'}
                </td>
                <td class="text-right ${stock.percent_change > 0 ? 'change-positive' : stock.percent_change < 0 ? 'change-negative' : 'change-0'}">
                    ${stock.percent_change.toFixed(2)}%
                </td>
            `;
            tbody.appendChild(tr);
        });

        document.querySelectorAll('.stock-link').forEach(link => {
            link.addEventListener('click', function (event) {
                event.preventDefault();
                openStockPopup(this.getAttribute('data-code'));
            });
        });
    }

    // 주식 상세 팝업 열기
    function openStockPopup(stockCode) {
        const width = Math.round(window.screen.width * 0.75);
        const height = Math.round(window.screen.height * 0.75);
        const left = Math.round((window.screen.width - width) / 2);
        const top = Math.round((window.screen.height - height) / 3);
        const popupWindow = window.open(`/stock_kr_detail?code=${stockCode}`, 'StockDetailPopup', `width=${width},height=${height},left=${left},top=${top}`);
        popupWindow.focus();
    }

    // 오류 메시지 표시
    function showError(message) {
        const errorDiv = document.getElementById('error-message');
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }

    // 초기 실행
    await checkLoginStatus(); // 로그인 상태 확인
    await fetchInitialStockData(); // 주식 목록 불러오기
    setInterval(fetchRealTimeStockData, 10000); // 10초마다 주식 데이터 갱신
});
