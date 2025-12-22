from pathlib import Path
import re

def extract_variable_delimiter_logs(ftg_path: str, output_dir: str, max_logs: int = 20):
    # ❶ 로그 시작 지점: 괄호 안 7자리 숫자
    pattern = re.compile(br"\(\d{8}\)")

    # ❷ 로그 분리 기준: 100개 이상 연속된 '@' (적절한 조절 가능)
    delimiter_pattern = re.compile(br"@{3,}")

    with open(ftg_path, "rb") as f:
        data = memoryview(f.read())

    # ➌ 로그 시작 위치
    match = pattern.search(data)
    if not match:
        raise ValueError("로그 시작 패턴 (7자리 괄호 숫자)을 찾을 수 없습니다.")
    start = match.start()

    # ➍ 이후 로그 영역 추출
    log_section = data[start:]

    # ➎ 골뱅이 연속 구간 기준으로 분할
    split_logs = delimiter_pattern.split(log_section)

    # ➏ 출력 폴더 생성
    output = Path(output_dir)
    output.mkdir(exist_ok=True, parents=True)

    # ➐ 저장
    for i, chunk in enumerate(split_logs[:max_logs]):
        try:
            text = chunk.decode("utf-8", errors="replace").strip()
            (output / f"log_{i+1:02d}.txt").write_text(text, encoding="utf-8")
        except Exception as e:
            print(f"로그 {i+1} 저장 실패: {e}")

if __name__ == "__main__":
    ftg_path = "/Users/mikchip/Downloads/inquiry/uart_buffer_full/example.ftg"  # FTG 파일 경로
    output_dir = "/Users/mikchip/Downloads/inquiry/uart_buffer_full/output/logs"  # 로그 저장할 디렉토리 경로
    max_logs = 20  # 최대 로그 개수
    extract_variable_delimiter_logs(ftg_path, output_dir, max_logs)