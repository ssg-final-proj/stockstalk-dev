document.addEventListener("DOMContentLoaded", () => {
    const currencyPairButtons = document.querySelectorAll(".currency-pair");
    const currencyPairInput = document.getElementById("currency_pair");
    const amountInput = document.getElementById("amount");
    const expectedAmountDisplay = document.getElementById("expected_amount");

    let selectedPair = "KRW_to_USD";

    // 통화쌍 버튼 클릭 이벤트
    currencyPairButtons.forEach((button) => {
        button.addEventListener("click", function () {
            currencyPairButtons.forEach((btn) => btn.classList.remove("selected"));
            this.classList.add("selected");

            selectedPair = this.getAttribute("data-pair");
            currencyPairInput.value = selectedPair;

            updateStepValue();
            updateExpectedAmount();
        });
    });

    // 금액 입력 시 예상 금액 업데이트
    amountInput.addEventListener("input", updateExpectedAmount);

    function updateStepValue() {
        if (selectedPair === "KRW_to_USD") {
            amountInput.step = "1000";
            amountInput.min = "0";
        } else if (selectedPair === "USD_to_KRW") {
            amountInput.step = "0.01";
            amountInput.min = "0";
        }
    }

    function updateExpectedAmount() {
        const inputAmount = parseFloat(amountInput.value) || 0;
        const exchangeRate = parseFloat(document.getElementById("exchange_rate").textContent);

        console.log(`Selected pair: ${selectedPair}`);  // 선택된 통화쌍 출력
        console.log(`Input amount: ${inputAmount}`);    // 입력된 금액 출력
        console.log(`Exchange rate: ${exchangeRate}`);  // 환율 출력

        if (inputAmount < 0) {
            showMessage("금액은 0 미만일 수 없습니다.");
            return;
        }

        // 서버로 사용자 잔액 요청
        fetch(`${window.CONFIG.EXCHANGE_SERVICE_URL}/get_balance`, {  // ✅ 절대 URL 사용
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"  // ✅ 서버에 JSON 요청 명시
            },
            body: JSON.stringify({ currency_pair: selectedPair })
        })        
            .then((response) => response.json())
            .then((data) => {
                console.log(data);  // 서버 응답 출력
                if (data.error) {
                    showMessage(data.error);
                    return;
                }
                
                const userBalance = data.balance;
                console.log(`User balance: ${userBalance}`);  // 사용자 잔액 출력

                let expectedAmount = 0;
                let suffix = "";

                if (selectedPair === "KRW_to_USD") {
                    if (inputAmount < 1000) {
                        showMessage("최소 환전 단위는 1000 KRW입니다.");
                        return;
                    }
                    if (inputAmount > userBalance) {
                        showMessage("보유 원화 금액을 초과했습니다!");
                        return;
                    }
                    expectedAmount = (inputAmount / exchangeRate).toFixed(2);
                    suffix = "USD";
                } else if (selectedPair === "USD_to_KRW") {
                    if (inputAmount < 1) {
                        showMessage("최소 환전 단위는 1 USD입니다.");
                        return;
                    }
                    if (inputAmount > userBalance) {
                        showMessage("보유 달러 금액을 초과했습니다!");
                        return;
                    }
                    expectedAmount = Math.round(inputAmount * exchangeRate);  // 정수로 변환
                    suffix = "KRW";
                }

                console.log(`Expected amount: ${expectedAmount}`);  // 예상 환전 금액 출력
                showMessage(`예상 환전 금액: ${expectedAmount} ${suffix}`);
            })
            .catch((error) => {
                console.error("잔액 정보를 가져오는 중 오류 발생:", error);
                showMessage("잔액 정보를 가져오는 데 실패했습니다.");
            });
    }

    function showMessage(msg) {
        // 원화 금액에 천 단위 콤마 추가, 소수점 제거
        const formattedMessage = msg.replace(/\d(?=(\d{3})+(?!\d))/g, '$&,');
        expectedAmountDisplay.textContent = formattedMessage;
        expectedAmountDisplay.style.color = "greyblue";
        expectedAmountDisplay.style.display = "block";
    }

    function hideMessage() {
        expectedAmountDisplay.textContent = "";
        expectedAmountDisplay.style.display = "none";
    }
});
