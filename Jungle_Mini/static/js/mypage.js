// For mypage_main.html (Grade-specific data)
function handle_grade_data_edit(button) {
    const card = document.getElementById('basic-info-card');
    const gradeSelector = document.getElementById('grade-selector');
    const inputs = [
        document.getElementById('career-aspiration'),
        document.getElementById('average-grade')
    ];
    const isReadonly = inputs[0].hasAttribute('readonly');

    if (isReadonly) {
        // --- Switch to Edit Mode ---
        inputs.forEach(input => input.removeAttribute('readonly'));
        gradeSelector.setAttribute('disabled', 'true'); // Disable selector while editing
        button.textContent = '저장';
        button.classList.remove('btn-secondary');
        button.classList.add('btn-primary');
        inputs[0].focus(); // Set focus to the first input
    } else {
        // --- Switch to Save Mode ---
        const selectedGrade = gradeSelector.value;
        const payload = {
            main: {
                grade: selectedGrade,
                career_aspiration: inputs[0].value,
                average_grade: inputs[1].value
            }
        };

        apiRequest({
            type: "POST",
            url: "/mypage/save",
            contentType: "application/json",
            data: JSON.stringify(payload),
            success: function (response) {
                if (response.result === "success") {
                    alert("저장 성공");
                    // Update the global data object
                    gradeData[selectedGrade] = payload.main;

                    // Revert to Read-only mode
                    inputs.forEach(input => input.setAttribute('readonly', 'true'));
                    gradeSelector.removeAttribute('disabled');
                    button.textContent = '수정';
                    button.classList.remove('btn-primary');
                    button.classList.add('btn-secondary');
                } else {
                    alert("저장 실패: " + response.message);
                }
            },
            error: function(xhr) {
                alert("저장 중 오류가 발생했습니다.");
            }
        });
    }
}

// For other pages like activities, specialty
function toggle_and_save(cardId, button, dataType) {
    const card = document.getElementById(cardId);
    const inputs = card.querySelectorAll('.input-data');

    if (dataType === 'specialty') {
        // For specialty, the button is always '저장' and inputs are always editable.
        // This function will only trigger the save logic.
        let payload = {};
        let data = [];
        const item_groups = card.querySelectorAll('.index');
        item_groups.forEach(group => {
            let item_data = {};
            group.querySelectorAll('input, textarea').forEach(input => {
                item_data[input.name] = input.value;
            });
            if (Object.values(item_data).some(val => val !== '')) {
                data.push(item_data);
            }
        });
        payload[dataType] = data;

        console.log(`Saving ${dataType} data payload:`, JSON.stringify(payload)); // DEBUGGING

        // AJAX call to save data
        apiRequest({
            type: "POST",
            url: "/mypage/save",
            contentType: "application/json",
            data: JSON.stringify(payload),
            success: function (response) {
                if (response.result === "success") {
                    alert("저장 성공");
                } else {
                    alert("저장 실패: " + response.message);
                }
            },
            error: function(xhr) {
                alert("저장 중 오류가 발생했습니다.");
            }
        });
    } else { // For other pages like activities
        const isReadonly = inputs[0].hasAttribute('readonly') || inputs[0].hasAttribute('disabled');

        if (isReadonly) {
            // --- Switch to Edit Mode ---
            inputs.forEach(input => {
                input.removeAttribute('readonly');
                input.removeAttribute('disabled');
            });
            button.textContent = '저장';
            button.classList.remove('btn-secondary');
            button.classList.add('btn-primary');
        } else {
            // --- Switch to Save Mode ---
            let payload = {};
            let data;

            if (dataType === 'activities') {
                data = {};
                inputs.forEach(input => {
                    data[input.id] = input.value;
                });
            }
            payload[dataType] = data;

            console.log(`Saving ${dataType} data payload:`, JSON.stringify(payload)); // DEBUGGING

            // AJAX call to save data
            apiRequest({
                type: "POST",
                url: "/mypage/save",
                contentType: "application/json",
                data: JSON.stringify(payload),
                success: function (response) {
                    if (response.result === "success") {
                        alert("저장 성공");
                        // Revert to Read-only mode
                        inputs.forEach(input => {
                            if(input.tagName === 'SELECT') {
                                input.setAttribute('disabled', 'true');
                            } else {
                                input.setAttribute('readonly', 'true');
                            }
                        });
                        button.textContent = '수정';
                        button.classList.remove('btn-primary');
                        button.classList.add('btn-secondary');
                    } else {
                        alert("저장 실패: " + response.message);
                    }
                },
                error: function(xhr) {
                    alert("저장 중 오류가 발생했습니다.");
                }
            });
        }
    }
}

// --- Functions to Add New Input Rows --- //
function add_specialty_input() {
    const context = document.getElementById("specialty-context");
    const temp = `<div class="index form-group">
        <input class="input-data subject" name="과목" type="text" placeholder="과목명">
        <textarea class="input-data activity" name="활동" placeholder="활동 내용을 기입해주세요." rows="1"></textarea>
        <button class="btn btn-danger" onclick="delete_specialty_item(this)">삭제</button>
    </div>`;
    context.insertAdjacentHTML("beforeend", temp);
}

function delete_specialty_item(buttonElement) {
    const itemGroup = buttonElement.closest('.index');
    const subject = itemGroup.querySelector('.subject').value;
    const activity = itemGroup.querySelector('.activity').value;

    // If both subject and activity are empty, assume it's a newly added, unsaved item
    if (!subject && !activity) {
        itemGroup.remove(); // Remove from UI only
        return;
    }

    apiRequest({
        type: "POST",
        url: "/mypage/delete_specialty",
        contentType: "application/json",
        data: JSON.stringify({ subject: subject, activity: activity }),
        success: function (response) {
            if (response.success) {
                itemGroup.remove(); // Remove from UI
            } else {
                // Optionally log to console for debugging if needed
                console.error("삭제 실패:", response.message);
            }
        },
        error: function(xhr) {
            // Optionally log to console for debugging if needed
            console.error("삭제 중 오류 발생:", xhr);
        }
    });
}