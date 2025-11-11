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
    const resetGameBtn = document.getElementById('reset-game');

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


    resetGameBtn.addEventListener('click', () => {

        const gameSettings = {
            cpu_opponents: parseInt(cpuOpponents.value, 10),
            ai_opponents: {
                aggressor: parseInt(aiAggressor.value, 10),
                farmer: parseInt(aiFarmer.value, 10),
                survivor: parseInt(aiSurvivor.value, 10),
            },
            food: parseInt(foodSlider.value, 10),
            viruses: parseInt(virusSlider.value, 10),
        };

        console.log('JavaScript is sending these settings to Python:', gameSettings);

        try {
            // PyScript exports functions to the global scope
            if (typeof reset_game_from_js !== 'undefined') {
                reset_game_from_js(gameSettings);
                console.log('Successfully called Python function.');
            } else {
                // Wait a bit and try again if PyScript is still loading
                setTimeout(() => {
                    if (typeof reset_game_from_js !== 'undefined') {
                        reset_game_from_js(gameSettings);
                        console.log('Successfully called Python function (delayed).');
                    } else {
                        console.error('Python function reset_game_from_js not found. Is PyScript loaded?');
                        alert('Error: Could not communicate with the Pygame script. Make sure PyScript is fully loaded.');
                    }
                }, 500);
            }
        } catch (error) {
            console.error('Failed to call Python function from JavaScript:', error);
            alert('Error: Could not communicate with the Pygame script. Make sure PyScript is fully loaded.');
        }
    });
});
