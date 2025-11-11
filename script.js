document.addEventListener('DOMContentLoaded', () => {
    const cpuOpponents = document.getElementById('cpu-opponents');
    const aiAggressor = document.getElementById('ai-aggressor');
    const aiFarmer = document.getElementById('ai-farmer');
    const aiSurvivor = document.getElementById('ai-survivor');
    const shuffleAi = document.getElementById('shuffle-ai');
    const foodSlider = document.getElementById('food-slider');
    const foodValue = document.getElementById('food-value');
    const virusSlider = document.getElementById('virus-slider');
    const virusValue = document.getElementById('virus-value');
    const resetGame = document.getElementById('reset-game');

    foodSlider.addEventListener('input', () => {
        foodValue.textContent = foodSlider.value;
    });

    virusSlider.addEventListener('input', () => {
        virusValue.textContent = virusSlider.value;
    });

    shuffleAi.addEventListener('click', () => {
        aiAggressor.value = Math.floor(Math.random() * 6);
        aiFarmer.value = Math.floor(Math.random() * 6);
        aiSurvivor.value = Math.floor(Math.random() * 6);
    });

    resetGame.addEventListener('click', () => {
        const gameSettings = {
            cpu_opponents: parseInt(cpuOpponents.value),
            ai_opponents: {
                aggressor: parseInt(aiAggressor.value),
                farmer: parseInt(aiFarmer.value),
                survivor: parseInt(aiSurvivor.value),
            },
            food: parseInt(foodSlider.value),
            viruses: parseInt(virusSlider.value),
        };
        console.log('Resetting game with settings:', gameSettings);
        // In a real implementation, you would send these settings to the Pygame app
    });
});
