/**
 * Recovery Page JavaScript
 * OTP input UX with auto-focus, auto-submit, and countdown timer
 */
document.addEventListener('DOMContentLoaded', () => {
    // --- OTP digit input handling ---
    const digits = document.querySelectorAll('.otp-digit');
    const hiddenInput = document.getElementById('otp-hidden');
    const otpForm = document.getElementById('otp-form');

    if (digits.length > 0) {
        // Focus first input
        digits[0].focus();

        digits.forEach((input, index) => {
            input.addEventListener('input', (e) => {
                const val = e.target.value;

                // Allow only digits
                if (!/^\d$/.test(val)) {
                    e.target.value = '';
                    return;
                }

                // Move to next
                if (index < digits.length - 1) {
                    digits[index + 1].focus();
                }

                // Update hidden field
                updateHiddenOTP();

                // Auto-submit when all filled
                if (index === digits.length - 1) {
                    const allFilled = Array.from(digits).every(d => d.value.length === 1);
                    if (allFilled) {
                        updateHiddenOTP();
                        // Small delay for UX
                        setTimeout(() => otpForm.submit(), 300);
                    }
                }
            });

            input.addEventListener('keydown', (e) => {
                // Backspace handling
                if (e.key === 'Backspace') {
                    if (input.value === '' && index > 0) {
                        digits[index - 1].focus();
                        digits[index - 1].value = '';
                    } else {
                        input.value = '';
                    }
                    updateHiddenOTP();
                    e.preventDefault();
                }

                // Arrow keys
                if (e.key === 'ArrowLeft' && index > 0) {
                    digits[index - 1].focus();
                }
                if (e.key === 'ArrowRight' && index < digits.length - 1) {
                    digits[index + 1].focus();
                }
            });

            // Handle paste
            input.addEventListener('paste', (e) => {
                e.preventDefault();
                const pasted = (e.clipboardData || window.clipboardData).getData('text').trim();
                if (/^\d{6}$/.test(pasted)) {
                    digits.forEach((d, i) => {
                        d.value = pasted[i];
                    });
                    digits[digits.length - 1].focus();
                    updateHiddenOTP();
                    setTimeout(() => otpForm.submit(), 300);
                }
            });

            // Select on focus
            input.addEventListener('focus', () => {
                input.select();
            });
        });
    }

    function updateHiddenOTP() {
        if (hiddenInput) {
            hiddenInput.value = Array.from(digits).map(d => d.value).join('');
        }
    }

    // --- Countdown Timer ---
    const countdown = document.getElementById('timer-countdown');
    if (countdown) {
        let totalSeconds = 10 * 60; // 10 minutes

        const timerInterval = setInterval(() => {
            totalSeconds--;
            if (totalSeconds <= 0) {
                clearInterval(timerInterval);
                countdown.textContent = 'EXPIRED';
                countdown.style.color = '#ff1744';
                // Disable form
                const btn = document.getElementById('verify-otp-btn');
                if (btn) {
                    btn.disabled = true;
                    btn.style.opacity = '0.5';
                    btn.textContent = 'OTP Expired — Request New';
                }
                return;
            }

            const min = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
            const sec = (totalSeconds % 60).toString().padStart(2, '0');
            countdown.textContent = `${min}:${sec}`;

            // Red when under 1 minute
            if (totalSeconds < 60) {
                countdown.style.color = '#ff1744';
            }
        }, 1000);
    }
});
