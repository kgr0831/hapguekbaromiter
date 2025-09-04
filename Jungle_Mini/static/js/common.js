function getCookie(name) {
    const nameEQ = name + "=";
    const ca = document.cookie.split(';');
    for(let i=0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
}

/* 
    토큰 확인이 필요한 요청을 보낼 때에 사용함

    - 사용법

    : 상단에 <script src="/static/js/common.js"></script> 선언
    : $.ajax({...}) 대신 apiRequest({...})로 호출
    : @app.route(...) 아래에 @jwt_required()를 기입
*/
function apiRequest(options) {
    const defaultOptions = {
        xhrFields: { withCredentials: true }, // 쿠키 전송
        beforeSend: function(xhr, settings) {
            // Only add CSRF token for non-GET requests
            if (settings.type !== 'GET') {
                const csrfToken = getCookie('csrf_access_token');
                if (csrfToken) {
                    xhr.setRequestHeader('X-CSRF-TOKEN', csrfToken);
                }
            }
        }
    };

    // $.ajax 호출
    return $.ajax({
        ...defaultOptions,
        ...options
    }).fail(async function (xhr) {
        if (xhr.status === 401 && !options._retry) {// Access토큰 만료 시 
            try {
                const refreshResult = await $.ajax({
                    type: "POST",
                    url: "/REFRESH",
                    xhrFields: { withCredentials: true }
                });

                if (refreshResult.result === "success") {//refresh에 성공했다면
                    options._retry = true; // 무한 루프 방지
                    return apiRequest(options); // 기존 요청 이어서 진행
                }
            } catch (err) {
                console.error("토큰 재발급 실패:", err);
                alert("세션이 만료되었습니다. 다시 로그인 해주세요.");
            }
        }
    });
}