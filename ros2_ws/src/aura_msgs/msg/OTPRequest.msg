# OTPRequest.msg
# Topic: /aura/otp_request
std_msgs/Header header

int32  delivery_id
int32  user_id
string username
string phone_number
string otp_code            # Generated OTP (4-digit)
string action              # "send" | "verify" | "expire"
bool   verified            # True after successful verification
int32  attempts            # Number of verification attempts
int32  max_attempts        # Maximum allowed attempts (default: 3)
int32  timeout_seconds     # OTP validity window
