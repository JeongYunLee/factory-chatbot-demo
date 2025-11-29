import time
from functools import wraps

import openai
from openai import RateLimitError, APITimeoutError


def retry_on_failure(max_retries: int = 3, delay: int = 1):
    """
    OpenAI API 호출 등 실패 시 재시도하기 위한 데코레이터
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception: Exception | None = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:  # pylint: disable=broad-except
                    last_exception = e
                    if attempt < max_retries - 1:
                        print(f"⚠️ 시도 {attempt + 1} 실패, {delay}초 후 재시도: {str(e)[:100]}")
                        time.sleep(delay * (attempt + 1))  # 지수 백오프
                    else:
                        print(f"❌ 모든 재시도 실패: {str(e)}")
            # 여기까지 왔다는 것은 모든 재시도가 실패했다는 의미
            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator


@retry_on_failure(max_retries=3, delay=2)
def call_openai_with_retry(client: openai.OpenAI, **kwargs):
    """
    OpenAI Chat Completions API를 레이트리밋/타임아웃에 대비해 안전하게 호출
    """
    try:
        return client.chat.completions.create(**kwargs)
    except RateLimitError as e:
        print(f"⚠️ OpenAI 레이트 리미트: {e}")
        time.sleep(5)  # 레이트 리미트 시 더 오래 대기
        raise
    except APITimeoutError as e:
        print(f"⚠️ OpenAI 타임아웃: {e}")
        raise
    except Exception as e:  # pylint: disable=broad-except
        print(f"⚠️ OpenAI API 오류: {e}")
        raise


__all__ = ["retry_on_failure", "call_openai_with_retry"]


