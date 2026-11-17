const form = document.querySelector('#ieee-form');
const input = document.querySelector('#ieee-json');
const file = document.querySelector('#ieee-file');
const example = document.querySelector('#ieee-example');
const submit = document.querySelector('#submit');
const result = document.querySelector('#ieee-result');
const state = document.querySelector('#state');
const error = document.querySelector('#error');
const format = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 6 });

async function request(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Vérifie les champs de la transaction.');
  }
  return data;
}

function showError(failure) {
  error.textContent = failure.message;
  error.hidden = false;
}

const modelStatus = document.querySelector('#ieee-model-status');
request('/ieee/model-info').then(({ validation }) => {
  const percent = new Intl.NumberFormat('fr-FR', { style: 'percent', maximumFractionDigits: 1 });
  modelStatus.textContent = `Sur la validation : ${percent.format(validation.precision)} des alertes correctes · ${percent.format(validation.recall)} des fraudes détectées.`;
}).catch((failure) => { modelStatus.textContent = failure.message; });

file.addEventListener('change', async () => {
  if (!file.files.length) return;
  error.hidden = true;
  try {
    input.value = await file.files[0].text();
  } catch (failure) {
    showError(failure);
  }
});

example.addEventListener('click', async () => {
  error.hidden = true;
  example.disabled = true;
  try {
    input.value = JSON.stringify(await request('/ieee/example'), null, 2);
  } catch (failure) {
    showError(failure);
  } finally {
    example.disabled = false;
  }
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  submit.disabled = true;
  error.hidden = true;
  result.hidden = true;
  delete state.dataset.decision;
  state.textContent = 'Analyse en cours…';
  try {
    const transaction = JSON.parse(input.value);
    if (!transaction || typeof transaction !== 'object' || Array.isArray(transaction)) {
      throw new Error('Le fichier doit contenir un objet JSON représentant une transaction.');
    }
    const prediction = await request('/ieee/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(transaction),
    });
    document.querySelector('#score').textContent = format.format(prediction.score);
    document.querySelector('#threshold').textContent = format.format(prediction.threshold);
    result.hidden = false;
    state.dataset.decision = prediction.alert ? 'alert' : 'clear';
    state.textContent = prediction.alert ? 'Alerte déclenchée' : 'Aucune alerte';
  } catch (failure) {
    state.textContent = 'Analyse indisponible.';
    showError(failure instanceof SyntaxError ? new Error('Le JSON est invalide.') : failure);
  } finally {
    submit.disabled = false;
  }
});
