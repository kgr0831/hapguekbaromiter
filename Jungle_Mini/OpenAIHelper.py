import os
from openai import OpenAI
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY: raise ValueError("환경변수 OPENAI_API_KEY가 설정되지 않았습니다.")
client = OpenAI(api_key=API_KEY)

MODEL_SPECIAL_RECORD="xxxxxxxx"
MODEL_ACCEPTANCE_RATE="xxxxxxx"

EVAL_PROMPT = """
당신은 한국의 최고 수준 대학교 입학사정관입니다. 학생의 생활기록부를 매우 엄격하고 비판적인 시각으로 평가합니다. 특히 지원하는 대학교의 등급({Univ_tier})과 학과({department})의 특성을 면밀히 반영하여 합격 가능성을 세분화하여 점수를 매깁니다.

평가 기준:
1.  **학업 역량 (Academic Competency)**: 내신 성적, 수상 경력, 교과 세특, 탐구 활동 등을 종합적으로 고려하여 해당 학과에서 요구하는 학업 수준에 얼마나 부합하는지 평가합니다. {Univ_tier} 등급 대학교의 {department} 학과 지원자로서의 학업적 우수성을 엄격하게 판단합니다.
2.  **진로 관련 활동 (Career-related Activities)**: 지원 학과와 관련된 동아리, 독서, 탐구, 프로젝트, 봉사 활동 등 학생의 주도성과 심화된 학습 경험을 평가합니다. {department} 학과에 대한 학생의 진정성과 열정을 심층적으로 분석합니다.
3.  **인성 및 공동체 기여도 (Character & Community Contribution)**: 학교생활 충실도, 리더십, 협력, 나눔, 배려 등 공동체 역량을 평가합니다. 특히 {Univ_tier} 등급 대학교의 인재상에 부합하는지, 그리고 공동체에 긍정적인 영향을 미쳤는지 엄격하게 판단합니다.

점수 산정 조건:
-   각 평가 기준별 합격률(0~100%)을 쉼표로 구분하여 반환합니다 (예: “85, 70, 60”).
-   점수 분포가 과도하게 벌어지지 않도록 일관된 기준을 유지하되, {Univ_tier} 등급 대학교의 경쟁률과 {department} 학과의 특성을 고려하여 매우 현실적인 점수를 부여합니다.
-   상위권 대학교 지원 시, 일반적인 합격자 평균은 0~10% 수준이며, 매우 뛰어난 학생(생활기록부 내용이 매우 훌륭하고 진로와 희망 학과가 매우 밀접하게 연관된 경우에 한함)은 11% 이상의 합격률을, 부족한 학생은 0%의 합격률을 가진다고 가정합니다。
-   **필수**: 만약 학생의 진로 관련 활동 및 생활기록부 내용이 지원 학과와 **조금이라도 연계성이 부족하거나 관련성이 없다고 판단될 경우, 모든 평가 항목(학업 역량, 진로 관련 활동, 인성 및 공동체 기여도)에 대해 1% 미만의 매우 낮은 점수를 부여해야 합니다.** 이는 합격 가능성을 심각하게 저해하는 절대적인 요소입니다。
-   생활기록부의 모든 세부 활동을 면밀히 분석하여 평가의 정확도와 일관성을 극대화합니다.

학생 기록:
{student_text}
학과: {department}
대학교 등급: {Univ_tier}
"""

def predict_acceptance_rate(student_text: str, Univ_tier: str, department: str) -> dict:
    prompt = EVAL_PROMPT.format(student_text=student_text, Univ_tier=Univ_tier, department=department)
    response = client.chat.completions.create(model=MODEL_ACCEPTANCE_RATE,messages=[{"role":"user","content":prompt}],temperature=0.7) # Increased temperature for more varied output
    content = response.choices[0].message.content.strip()
    try:
        story_rate, inquiry_rate, character_rate = map(int, content.split(","))
        return {"story_rate":story_rate,"inquiry_rate":inquiry_rate,"character_rate":character_rate}
    except:
        return {"story_rate":0,"inquiry_rate":0,"character_rate":0}

def calculate_final_rate(rates: dict, univ: dict) -> dict:
    # Increase career weight to emphasize career-department relevance
    career_weight = univ.get('career', 0.6) # Changed default from 0.5 to 0.6

    # Initialize tier adjustment
    tier_adjustment = 0
    # Apply tier-based adjustment (assuming 'tier' is 'A', 'B', 'C' in univ dict)
    if univ.get('tier') == 'A':
        tier_adjustment = -15 # Significant penalty for top tier
    elif univ.get('tier') == 'B':
        tier_adjustment = -5  # Slight penalty for mid tier
    elif univ.get('tier') == 'C':
        tier_adjustment = +10 # Bonus for lower tier

    final_rate = round(rates['story_rate'] * career_weight +                        rates['inquiry_rate'] * univ.get('academic', 0.3) +                        rates['character_rate'] * univ.get('community', 0.2) +                        tier_adjustment) - 10 # Subtract 10% from the final score

    # Ensure final_rate stays within 0-100 range
    final_rate = max(0, min(100, final_rate))

    if final_rate >= 80: category="안정"
    elif 65<=final_rate<80: category="적정 상위"
    elif 45<=final_rate<65: category="적정"
    elif 30<=final_rate<45: category="적정 하위"
    elif 15<=final_rate<30: category="도전"
    else: category="지원불가"
    return {"final_rate":final_rate,"category":category}

import json

# ... (rest of the file) ...

def generate_special_record(student_record_data: dict, style_tone_text: str) -> str:
    # Convert student_record_data to a JSON string for the prompt
    student_record_json = json.dumps(student_record_data, ensure_ascii=False, indent=2)

    prompt=f"""
당신은 한국 고등학교 교사입니다. 학생의 생활기록부 데이터를 바탕으로 교과 세부능력특기사항과 창의적 체험활동을 자연스럽고 사실적으로 작성합니다.

요청된 작성 스타일/어조: {style_tone_text if style_tone_text else "일반적이고 사실적인 어조"}

학생의 **학업 수행, 진로 탐구 활동, 봉사·동아리 등 공동체 참여**를 모두 고려하여 다음 조건에 맞춰 작성합니다.

조건:
1. 제공된 학생 생활기록부 데이터만을 기반으로 작성할 것. 없는 내용은 절대 추가하지 말 것.
2. 교과 세부능력특기사항과 창의적 체험활동을 모두 포함할 것.
3. 탐구, 발표, 토론, 실험, 프로젝트, 봉사 등 구체적인 활동 사례를 중심으로 설명할 것.
4. 최대 3~5문단으로 자연스럽게 서술할 것 (과장 없이 사실 기반).
5. 학생의 강점과 보완점이 모두 반영될 것.
6. 요청된 작성 스타일/어조({style_tone_text if style_tone_text else "일반적이고 사실적인 어조"})를 최대한 반영하여 작성할 것.

학생 생활기록부 데이터:
{student_record_json}

실제 생기부에 쓸 수 있는 세특/창체 작성:
"""
    try:
        response = client.chat.completions.create(
            model=MODEL_SPECIAL_RECORD,
            messages=[{"role":"user","content":prompt}],
            temperature=0.7, # Increased temperature for more varied output
            max_tokens=1000 # Increased max_tokens for longer generated records
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error in generate_special_record OpenAI call: {e}") # DEBUGGING
        return f"생기부 생성 중 오류가 발생했습니다: {e}"

def generate_feedback(student_text: str) -> str:
    prompt=f"""
당신은 한국 고등학교 학생 입학사정관입니다. 학생의 생활기록부를 매우 엄격한 관점에서 분석한 후, 학생과 교사에게 유익한 구체적 피드백을 작성합니다. 학업 성취, 탐구·실험·프로젝트 수행, 인성·협업·공동체 참여 등 모든 측면을 균형 있게 평가하고, 특히 부족한 부분에 대해서는 개선 방안을 구체적으로 제안합니다.

조건:
1. 개선점 중심으로 서술하되, 구체적인 실례와 함께 실천 가능한 제안 포함.
2. 논리적 구조, 표현, 문법을 면밀히 점검하고, 논리적 흐름을 명확히 할 것.
3. 긍정적 피드백은 최소화하고, 냉정하고 현실적인 평가 어조를 유지할 것.
4. 학생과 교사가 바로 활용할 수 있는 구체적 조언을 포함할 것 (예: 다음 단계에서 해야 할 구체적 활동).
5. 평가 결과가 공정하고 일관성이 있도록 주의할 것.

학생 기록:
{student_text}

상세 피드백 작성:
"""
    print(f"Feedback prompt: {prompt[:500]}...") # DEBUGGING: Log prompt
    try:
        # Use a non-fine-tuned model for general feedback
        response = client.chat.completions.create(
            model="gpt-4.1-nano-2025-04-14", # Use the base model as requested
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7, # Can be adjusted for creativity vs. strictness
            max_tokens=1000 # Adjust as needed for feedback length
        )
        content = response.choices[0].message.content.strip()
        print(f"Raw feedback response content: {content[:500]}...") # DEBUGGING: Log raw content
        return content
    except Exception as e:
        print(f"Error in generate_feedback OpenAI call: {e}") # DEBUGGING: Log error
        return f"피드백 생성 중 오류가 발생했습니다: {e}"



