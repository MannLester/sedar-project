(function () {
    function ready(callback) {
        if (document.readyState !== 'loading') {
            callback();
            return;
        }
        document.addEventListener('DOMContentLoaded', callback);
    }

    ready(function () {
        var form = document.querySelector('.o_sedar_applicant_form');
        if (!form) {
            return;
        }

        var steps = Array.prototype.slice.call(form.querySelectorAll('.o_sedar_applicant_step'));
        var stepButtons = Array.prototype.slice.call(form.querySelectorAll('[data-step-target]'));
        var currentStep = 0;
        var maxBytes = 10 * 1024 * 1024;

        function setStep(index) {
            currentStep = Math.max(0, Math.min(index, steps.length - 1));
            steps.forEach(function (step, stepIndex) {
                step.classList.toggle('is-active', stepIndex === currentStep);
            });
            stepButtons.forEach(function (button, buttonIndex) {
                button.classList.toggle('is-active', buttonIndex === currentStep);
            });
            form.classList.toggle('is-final-step', currentStep === steps.length - 1);
        }

        function inputValue(input) {
            if (input.type === 'checkbox') {
                return input.checked ? 'checked' : '';
            }
            if (input.type === 'file') {
                return input.files && input.files.length ? 'file' : '';
            }
            return (input.value || '').trim();
        }

        function validateScope(scope) {
            var valid = true;
            var inputs = Array.prototype.slice.call(scope.querySelectorAll('[data-required="1"]'));
            inputs.forEach(function (input) {
                var isFilled = Boolean(inputValue(input));
                var fileTooLarge = false;
                if (input.type === 'file' && input.files && input.files[0]) {
                    fileTooLarge = input.files[0].size > maxBytes;
                }
                input.classList.toggle('o_sedar_is_invalid', !isFilled || fileTooLarge);
                if (!isFilled || fileTooLarge) {
                    valid = false;
                }
            });
            return valid;
        }

        function syncDetails() {
            Array.prototype.slice.call(form.querySelectorAll('[data-detail-toggle]')).forEach(function (select) {
                var detail = form.querySelector('[name="' + select.dataset.detailToggle + '"]');
                if (!detail) {
                    return;
                }
                var wrapper = detail.closest('label');
                var visible = select.value === 'yes';
                if (wrapper) {
                    wrapper.classList.toggle('is-visible', visible);
                }
                detail.dataset.required = visible ? '1' : '0';
            });
        }

        stepButtons.forEach(function (button, index) {
            button.addEventListener('click', function () {
                if (index <= currentStep || validateScope(steps[currentStep])) {
                    setStep(index);
                }
            });
        });

        form.querySelector('[data-step-next]').addEventListener('click', function () {
            if (validateScope(steps[currentStep])) {
                setStep(currentStep + 1);
            }
        });

        form.querySelector('[data-step-prev]').addEventListener('click', function () {
            setStep(currentStep - 1);
        });

        Array.prototype.slice.call(form.querySelectorAll('[data-add-row]')).forEach(function (button) {
            button.addEventListener('click', function () {
                var group = form.querySelector('[data-repeat-group="' + button.dataset.addRow + '"]');
                var row = group && group.querySelector('.o_sedar_repeat_row');
                if (!group || !row) {
                    return;
                }
                var clone = row.cloneNode(true);
                Array.prototype.slice.call(clone.querySelectorAll('input, textarea, select')).forEach(function (input) {
                    input.value = '';
                    input.classList.remove('o_sedar_is_invalid');
                });
                group.appendChild(clone);
            });
        });

        form.addEventListener('change', function (event) {
            if (event.target.matches('[data-detail-toggle]')) {
                syncDetails();
            }
            if (event.target.matches('.o_sedar_is_invalid') && inputValue(event.target)) {
                event.target.classList.remove('o_sedar_is_invalid');
            }
        });

        form.addEventListener('submit', function (event) {
            syncDetails();
            var valid = steps.every(validateScope);
            if (!valid) {
                event.preventDefault();
                var firstInvalid = form.querySelector('.o_sedar_is_invalid');
                var invalidStep = firstInvalid && firstInvalid.closest('.o_sedar_applicant_step');
                if (invalidStep) {
                    setStep(steps.indexOf(invalidStep));
                }
            }
        });

        syncDetails();
        setStep(0);
    });
})();
