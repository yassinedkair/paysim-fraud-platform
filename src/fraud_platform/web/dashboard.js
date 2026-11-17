const form = document.querySelector('#transaction-form');
const submit = document.querySelector('#submit');
const state = document.querySelector('#state');
const result = document.querySelector('#result');
const error = document.querySelector('#error');
const type = form.elements.transaction_type;
const amount = form.elements.amount;
const hour = form.elements.hour_of_day;
const formatScore = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 4 });
const formatAmount = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 8 });

async function showModelMetrics() {
  try {
    const response = await fetch('/model-info');
    if (!response.ok) return;
    const { validation } = await response.json();
    if (!Number.isFinite(validation?.precision) || !Number.isFinite(validation?.recall)) return;
    const percent = new Intl.NumberFormat('fr-FR', { style: 'percent', maximumFractionDigits: 1 });
    const metrics = document.querySelector('#model-metrics');
    metrics.textContent = `Sur la validation PaySim : ${percent.format(validation.precision)} des alertes correctes · ${percent.format(validation.recall)} des fraudes détectées.`;
    metrics.hidden = false;
  } catch {
    // Le formulaire conserve sa gestion d'erreur lors d'une demande de scoring.
  }
}

showModelMetrics();

document.querySelectorAll('[data-type]').forEach((preset) => {
  preset.addEventListener('click', () => {
    type.value = preset.dataset.type;
    amount.value = preset.dataset.amount;
    hour.value = preset.dataset.hour;
    type.focus();
  });
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const transaction = {
    transaction_type: type.value,
    amount: amount.valueAsNumber,
    hour_of_day: hour.valueAsNumber,
  };
  const operation = type.selectedOptions[0].text;
  submit.disabled = true;
  result.hidden = true;
  error.hidden = true;
  state.removeAttribute('data-decision');
  state.textContent = 'Analyse en cours…';

  try {
    const response = await fetch('/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(transaction),
    });
    if (!response.ok) {
      throw new Error(response.status === 422
        ? 'Vérifie le type, le montant et l’heure de la transaction.'
        : 'Le service de scoring est indisponible. Réessaie dans un instant.');
    }
    const prediction = await response.json();
    document.querySelector('#transaction-summary').textContent =
      `${operation} · ${formatAmount.format(transaction.amount)} unités · ${transaction.hour_of_day} h`;
    document.querySelector('#score').textContent = formatScore.format(prediction.score);
    document.querySelector('#threshold').textContent = formatScore.format(prediction.threshold);
    document.querySelector('#score-fill').style.width = `${prediction.score * 100}%`;
    document.querySelector('#threshold-mark').style.left = `${prediction.threshold * 100}%`;
    result.hidden = false;
    state.dataset.decision = prediction.alert ? 'alert' : 'clear';
    state.textContent = prediction.alert ? 'Alerte déclenchée' : 'Aucune alerte';
  } catch (failure) {
    state.textContent = 'Analyse indisponible.';
    error.textContent = failure instanceof TypeError
      ? 'Impossible de joindre le service de scoring. Vérifie que FastAPI est lancé.'
      : failure.message;
    error.hidden = false;
  } finally {
    submit.disabled = false;
  }
});
