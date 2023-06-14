function toggleNFTCards(event) {
    event.preventDefault();
    // Get the NFT cards container element
    const nftCardsContainer = document.getElementById('nft-cards-container');
    // Toggle the visibility of the NFT cards container
    nftCardsContainer.style.display = nftCardsContainer.style.display === 'none' ? 'block' : 'none';
    // Update the link text based on the visibility state
    event.target.textContent = nftCardsContainer.style.display === 'none' ? 'Collectibles' : 'Hide Collectibles';
}

function toggleCalculator() {
    const calculatorFields = document.querySelectorAll('.calculator-fields');
    calculatorFields.forEach(field => {
        field.classList.toggle('show');
    });
    // Hide totalFloor and show calculatedFloor
    const totalFloor = document.querySelector('.totalFloor');
    const calculatedFloor = document.querySelector('.calculatedFloor');
    totalFloor.style.display = totalFloor.style.display === 'none' ? 'block' : 'none';
    calculatedFloor.style.display = calculatedFloor.style.display === 'none' ? 'block' : 'none';
}

function calculateTotal() {
    const quantityInputs = document.querySelectorAll('.nft-quantity');
    let totalSOL = 0;
    let totalCurrency = 0;

    quantityInputs.forEach(input => {
        const quantity = parseInt(input.value);
        const floorPrice = parseFloat(input.dataset.floorPrice);
        const currencyPrice = parseFloat(input.dataset.currencyPrice);
        const subtotalSOL = quantity * (floorPrice / 1000000000);
        const subtotalCurrency = quantity * (floorPrice / 1000000000 * currencyPrice);

        totalSOL += subtotalSOL;
        totalCurrency += subtotalCurrency;
    });

    return {
        totalSOL,
        totalCurrency
    };
}

function updateTotal() {
    const totalSOLField = document.getElementById('total-sol-amount');
    const totalCurrencyField = document.getElementById('total-currency-amount');
    const { totalSOL, totalCurrency } = calculateTotal();

    totalSOLField.textContent = totalSOL.toFixed(2);
    totalCurrencyField.textContent = totalCurrency.toFixed(2);
}

// Add event listener to quantity inputs
const quantityInputs = document.querySelectorAll('.nft-quantity');
quantityInputs.forEach(input => {
    input.addEventListener('input', updateTotal);
});