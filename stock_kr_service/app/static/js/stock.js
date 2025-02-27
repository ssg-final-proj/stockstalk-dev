document.addEventListener('DOMContentLoaded', function () {
    fetchStockData();
    setInterval(fetchStockData, 10000);  // 5초마다 데이터 업데이트
});

function fetchStockData() {
    fetch('/stock_kr/get_stock_data')
        .then(response => response.json())
        .then(data => {
            if (data.length > 0) {
                renderStockData(data);
            } else {
                console.error('No valid stock data available');
            }
        })
        .catch(error => {
            console.error('Error fetching stock data:', error);
        });
}

function renderStockData(stockData) {
    const stockListContainer = document.querySelector('tbody');

    if (!stockListContainer) {
        console.error('Stock list container not found');
        return;
    }

    stockListContainer.innerHTML = ''; // 기존 데이터 초기화

    stockData.forEach(stock => {
        const stockRow = document.createElement('tr');

        // 변동률 및 현재 가격에 따른 클래스 적용
        let changeClass = 'change-percent-0'; // 기본은 0으로 설정
        if (stock.regularMarketChange > 0) {
            changeClass = 'change-percent-positive'; // 상승
        } else if (stock.regularMarketChange < 0) {
            changeClass = 'change-percent-negative'; // 하락
        }

        stockRow.innerHTML = `
            <td><a href="#" class="stock-link" data-symbol="${stock.symbol}">${stock.shortName}</a></td>
            <td class="${changeClass}"><strong>${stock.regularMarketPrice.toLocaleString()} KRW</strong></td>
            <td class="change ${changeClass}">
                ${stock.regularMarketChange > 0 ? '+' : ''}${stock.regularMarketChange.toLocaleString()} KRW
            </td>
            <td class="change ${changeClass}">
                ${parseFloat(stock.regularMarketChangePercent).toFixed(2)}%
            </td>
        `;

        stockListContainer.appendChild(stockRow);
    });

    // 종목 이름 클릭 시 팝업 열기 기능 추가
    const stockLinks = document.querySelectorAll(".stock-link");
    stockLinks.forEach(link => {
        link.addEventListener("click", (event) => {
            event.preventDefault();
            const symbol = link.getAttribute("data-symbol");
            console.log('Stock symbol clicked:', symbol);
            openStockPopup(symbol);
        });
    });
}

function openStockPopup(symbol) {
    if (!symbol) {
        console.error('Invalid stock symbol');
        return;
    }
    const popupUrl = `/stock_kr_detail/stock_detail?symbol=${symbol}`;
    const popupOptions = "width=1200,height=800,scrollbars=yes,resizable=yes";
    window.open(popupUrl, "StockPopup", popupOptions);
}