$(document).ready(function () {
    // Hide the calculator fields initially
    $('.calculator-fields').hide();

    // Click event handler for "Enable calculator" link
    $('.enable-calculator-link').click(function (e) {
        e.preventDefault();
        toggleCalculator();
    });

    // Function to toggle calculator fields visibility
    function toggleCalculator() {
        $('.calculator-fields').toggle();
    }
});