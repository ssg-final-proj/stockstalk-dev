window.addEventListener('load', function() {
    const kakao_id = sessionStorage.getItem('kakao_id');
    
    if (kakao_id) {
        fetch('/auth/sessionSetup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ kakao_id: kakao_id })
        }).then(response => response.json())
        .then(data => {
            console.log("[DEBUG] Session setup response:", data);
        }).catch(error => {
            console.error("[DEBUG] Error setting up session:", error);
        });
    }
});
