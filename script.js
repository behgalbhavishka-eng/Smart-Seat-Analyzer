
document.addEventListener("DOMContentLoaded", function () {
    const seatButtons = document.querySelectorAll(".seat");
    const seatInput = document.getElementById("seat_id");
    const selectedLabel = document.getElementById("selected-seat-label");
    const clearButton = document.getElementById("clear-seat");

    let selectedSeat = null;

    function clearSelection() {
        if (selectedSeat) {
            selectedSeat.classList.remove("selected");
        }

        selectedSeat = null;

        if (seatInput) {
            seatInput.value = "";
        }

        if (selectedLabel) {
            selectedLabel.textContent =
                "No seat selected. The next available seat will be assigned automatically.";
        }
    }

    seatButtons.forEach(function (seat) {
        seat.addEventListener("click", function () {
            if (
                seat.disabled ||
                !seat.classList.contains("available")
            ) {
                return;
            }

            if (selectedSeat) {
                selectedSeat.classList.remove("selected");
            }

            selectedSeat = seat;
            selectedSeat.classList.add("selected");

            seatInput.value = seat.dataset.seatId;

            selectedLabel.textContent =
                "Selected seat: " + seat.dataset.seatNumber;
        });
    });

    if (clearButton) {
        clearButton.addEventListener("click", clearSelection);
    }
});
