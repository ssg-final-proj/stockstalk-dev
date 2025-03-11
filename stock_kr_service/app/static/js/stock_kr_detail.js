// 차트 스타일
let chartLayout = {
    title: '주식 캔들 차트',
    xaxis: {
        type: 'date',
        title: '시간',
        rangeslider: { visible: true },
        showspikes: true
    },
    yaxis: {
        title: '가격',
        showspikes: true
    },
    autosize: true,
    responsive: true,
    margin: { l: 50, r: 50, t: 50, b: 50 }
};

// 전역 변수로 현재 주식 코드 저장
let currentStockCode;
let currentStockData = null; // 현재 주식 데이터를 저장할 변수
let isOrderProcessing = false; // 주문 처리 중 여부

// DOMContentLoaded 이벤트 리스너
document.addEventListener('DOMContentLoaded', function () {
    // URL 파라미터에서 stockCode 가져오기
    currentStockCode = new URLSearchParams(window.location.search).get('code');
    if (!currentStockCode) {
        console.error('주식 코드가 없습니다.');
        showError('주식 코드를 찾을 수 없습니다.');
        return; // code가 없을 경우 여기서 중단
    }

    const kakaoId = getCookie('kakao_id');
    if (!kakaoId) {
        console.error('사용자 ID가 없습니다.');
        window.location.href = AUTH_SERVICE_URL;  // Config에서 가져온 URL 사용
        return;
    }

    fetchAndUpdateStockDetail(currentStockCode);
    fetchOrderHistory(currentStockCode); // 주문 내역 초기 로드

    // 매수/매도 버튼 이벤트 리스너 추가
    const buyToggle = document.getElementById('buy-toggle');
    const sellToggle = document.getElementById('sell-toggle');
    const chartToggle = document.getElementById('chart-toggle');
    const orderbookToggle = document.getElementById('orderbook-toggle');
    const buyForm = document.getElementById('buy-form');
    const sellForm = document.getElementById('sell-form');

    if (buyToggle) buyToggle.addEventListener('click', () => toggleOrderForm('BUY'));
    if (sellToggle) sellToggle.addEventListener('click', () => toggleOrderForm('SELL'));
    if (chartToggle) chartToggle.addEventListener('click', () => toggleView('chart'));
    if (orderbookToggle) orderbookToggle.addEventListener('click', () => toggleView('orderbook'));

    // 폼 제출 이벤트 리스너
    if (buyForm) {
        buyForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitOrder('BUY');
        });
    }

    if (sellForm) {
        sellForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitOrder('SELL');
        });
    }
    
    // 5초마다 주식 상세 정보를 업데이트합니다.
    setInterval(() => {
        fetchAndUpdateStockDetail(currentStockCode);
    }, 5000);
});

// 주식 상세 정보 가져오기
async function fetchAndUpdateStockDetail(stockCode) {
    console.log("[DEBUG] Fetching stock detail for code:", stockCode);

    try {
        const response = await fetch(`/api/stock-full-data?code=${stockCode}`);
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        const data = await response.json();

        if (data.error) {
            console.error('주식 데이터 오류:', data.error);
            showError(data.error);
            return;
        }

        console.log("[DEBUG] 주식 데이터 수신:", data);
        updateUI(data);
    } catch (error) {
        console.error('주식 상세 정보를 가져오는 중 오류 발생:', error);
        showError('주식 데이터를 가져오는 중 오류가 발생했습니다.');
    }
}

// UI 업데이트 함수
function updateUI(data) {
    currentStockData = data;
    const stockNameElement = document.getElementById('stock-name');
    const stockInfoElement = document.getElementById('stock-info');
    const stock = data;

    if (stock) {
        stockNameElement.textContent = stock.name || "알 수 없음";
        const stockChange = stock.change || 0;
        const stockColor = stockChange >= 0 ? 'red' : 'blue'; // 양수일 때 빨간색, 음수일 때 파란색
        stockInfoElement.innerHTML = `<span style="color: ${stockColor}">${stock.price || 0}원 (${stockChange}원, ${stock.percent_change || 0}%)</span>`;
        updateChart(stock.chart_data || {});
    } else {
        showError('해당 종목에 대한 데이터를 찾을 수 없습니다.');
    }
}

// 차트 업데이트 함수
function updateChart(chartData) {
    if (!chartData.timestamps || !chartData.open || !chartData.high || !chartData.low || !chartData.close) {
        console.error('잘못된 차트 데이터:', chartData);
        return;
    }

    console.log("[DEBUG] 차트 업데이트 데이터:", chartData);

    const transformedData = {
        x: chartData.timestamps,
        open: chartData.open.map(Number),
        high: chartData.high.map(Number),
        low: chartData.low.map(Number),
        close: chartData.close.map(Number)
    };

    const trace1 = {
        x: transformedData.x,
        open: transformedData.open,
        high: transformedData.high,
        low: transformedData.low,
        close: transformedData.close,
        type: 'candlestick',
        name: '캔들 차트',
        increasing: { line: { color: 'rgb(200, 0, 0)' } },
        decreasing: { line: { color: 'rgb(0, 113, 200)' } }
    };

    Plotly.react('chart', [trace1], chartLayout);
}

// 섹션 토글 함수
function toggleView(view) {
    const chartSection = document.getElementById('chart-section');
    const orderbookSection = document.getElementById('orderbook-section');
    const chartToggle = document.getElementById('chart-toggle');
    const orderbookToggle = document.getElementById('orderbook-toggle');

    if (view === 'chart') {
        chartSection.classList.remove('hidden');
        orderbookSection.classList.add('hidden');
        chartToggle.classList.add('active');
        orderbookToggle.classList.remove('active');
    } else {
        chartSection.classList.add('hidden');
        orderbookSection.classList.remove('hidden');
        chartToggle.classList.remove('active');
        orderbookToggle.classList.add('active');
    }
}

// 매수/매도 폼 토글 함수
function toggleOrderForm(orderType) {
    const buyForm = document.getElementById('buy-form');
    const sellForm = document.getElementById('sell-form');
    const buyToggle = document.getElementById('buy-toggle');
    const sellToggle = document.getElementById('sell-toggle');

    if (orderType === 'BUY') {
        buyForm.classList.add('active');
        buyForm.classList.remove('hidden');
        sellForm.classList.remove('active');
        sellForm.classList.add('hidden');
        buyToggle.classList.add('active');
        sellToggle.classList.remove('active');
    } else {
        buyForm.classList.remove('active');
        buyForm.classList.add('hidden');
        sellForm.classList.add('active');
        sellForm.classList.remove('hidden');
        buyToggle.classList.remove('active');
        sellToggle.classList.add('active');
    }
}

// 주문 처리 함수
async function submitOrder(orderType) {
    if (isOrderProcessing) {
        console.log('주문 처리 중입니다. 잠시 후 다시 시도해주세요.');
        return;
    }

    isOrderProcessing = true;
    const quantity = document.getElementById(`${orderType.toLowerCase()}-amount`).value;
    const price = document.getElementById(`${orderType.toLowerCase()}-price`).value;

    if (!currentStockCode) {
        showError('주식 코드를 찾을 수 없습니다.');
        return;
    }

    const kakaoId = getCookie('kakao_id');
    if (!kakaoId) {
        showError('로그인이 필요합니다.');
        window.location.href = AUTH_SERVICE_URL;  // Config에서 가져온 URL 사용
        return;
    }

    const orderData = {
        kakao_id: kakaoId,
        stock_symbol: currentStockCode,
        order_type: orderType,
        quantity: parseInt(quantity),
        target_price: parseFloat(price)
    };

    try {
        const response = await fetch(`/stock_kr_detail?code=${currentStockCode}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '주문 처리 중 오류 발생');
        }

        const result = await response.json();
        displaySuccess(result.message || '주문이 성공적으로 처리되었습니다.');  // 성공 메시지 표시
        fetchOrderHistory(currentStockCode); // 주문 성공 후 주문 내역 업데이트

    } catch (error) {
        console.error('주문 처리 중 오류 발생:', error);
        showError(error.message || '주문 처리 중 오류가 발생했습니다.'); // 오류 메시지 표시
    } finally {
        isOrderProcessing = false;
    }
}

// 폼 제출 방지 및 JavaScript로 처리
document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', function (event) {
        event.preventDefault(); // 기본 제출 동작 방지
        const orderType = form.id.includes('buy') ? 'BUY' : 'SELL';
        submitOrder(orderType);
    });
});

async function fetchOrderHistory(stockCode) {
    if (!stockCode) {
        console.error('주식 코드가 없습니다.');
        return;
    }
    const kakaoId = getCookie('kakao_id');
    if (!kakaoId) {
        console.error('사용자 ID가 없습니다.');
        return;
    }

    try {
        const response = await fetch(`${PORTFOLIO_SERVICE_URL}/api/order-history?code=${stockCode}&kakao_id=${kakaoId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log("[DEBUG] 주문 내역 데이터 수신:", data);
        updateOrderHistoryUI(data);
    } catch (error) {
        console.error('주문 내역을 가져오는 중 오류 발생:', error);
        updateOrderHistoryUI([]);  // 오류 발생 시 빈 배열로 UI 업데이트
    }
}

// 주문 내역 업데이트 함수 수정
function updateOrderHistoryUI(orders) {
    const orderList = document.getElementById('order-list');
    if (!orderList) {
        console.error('order-list 요소를 찾을 수 없습니다.');
        return;
    }
    orderList.innerHTML = ''; // 기존 목록 초기화

    if (orders.length === 0) {
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = '<td colspan="5">주문 내역이 없습니다.</td>';
        orderList.appendChild(emptyRow);
    } else {
        orders.forEach(order => {
            const row = document.createElement('tr');
            // 시간 형식을 시:분 으로 변경
            const formattedDate = new Date(order.date).toLocaleTimeString('ko-KR', {
                hour: '2-digit',
                minute: '2-digit',
                hour12: false // 24시간 형식 사용
            });
            row.innerHTML = `
                <td>${formattedDate}</td>
                <td>${order.type === 'BUY' ? '매수' : '매도'}</td>
                <td>${order.quantity}</td>
                <td>${order.price}</td>
            `;
            orderList.appendChild(row);
        });
    }
}

const socket = io('/stock');

socket.on('connect', function() {
    console.log('WebSocket 연결됨');
});

socket.on('order_update', function(data) {
    console.log('주문 업데이트 수신:', data);
    updateOrderHistory(data);
});

// 새로운 updateOrderHistory 함수를 추가합니다:
function updateOrderHistory(orderData) {
    const orderList = document.getElementById('order-list');
    if (!orderList) return;

    const newRow = document.createElement('tr');
    newRow.innerHTML = `
        <td>${orderData.date}</td>
        <td>${orderData.type}</td>
        <td>${orderData.quantity}주</td>
        <td>${orderData.price}원</td>
        <td>${orderData.status}</td>
    `;
    orderList.insertBefore(newRow, orderList.firstChild);
}
// 오류 메시지 표시 함수 (팝업)
function showError(message) {
    alert(message);
}

// 성공 메시지 표시 함수 (팝업)
function displaySuccess(message) {
    alert(message);
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}
