function onLoginSuccess(kakao_id) {
    sessionStorage.setItem('kakao_id', kakao_id);
    console.log("[DEBUG] User ID stored in session:", kakao_id);
}
