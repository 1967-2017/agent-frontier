const form = document.querySelector('#intake-form');
const confirmation = document.querySelector('#confirmation');
const cookieWall = document.querySelector('#cookie-wall');

for (const button of document.querySelectorAll('#accept-cookies, #continue-guest')) {
  button.addEventListener('click', () => {
    cookieWall.hidden = true;
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const requester = data.get('requester') || '未填写';
  const service = data.get('service') || '未填写';
  const route = data.get('route') || '未选择';
  const summary = data.get('summary') || '';

  if (form.dataset.networkDrop === 'true') {
    const status = document.querySelector('#network-status');
    try {
      const response = await fetch('/api/network-submit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({requester, service, route, summary}),
      });
      const payload = await response.json();
      if (!response.ok) {
        status.textContent = payload.message || '模拟断网中，请稍后重试';
        return;
      }
      showConfirmation(payload.confirmation, requester, service, route, summary);
      status.textContent = '网络已恢复，提交成功。';
      return;
    } catch (error) {
      status.textContent = '模拟断网中，请稍后重试';
      return;
    }
  }

  const confirmationId = `INC-${new Date().toISOString().slice(0, 10).replaceAll('-', '')}-0427`;
  showConfirmation(confirmationId, requester, service, route, summary);
});

function showConfirmation(confirmationId, requester, service, route, summary) {
  confirmation.hidden = false;
  confirmation.dataset.confirmation = confirmationId;
  confirmation.innerHTML = `
    <h2>提交成功</h2>
    <p><strong>确认编号：</strong> <span id="confirmation-number">${confirmationId}</span></p>
    <p><strong>请求人：</strong> <span id="submitted-requester">${requester}</span></p>
    <p><strong>服务：</strong> <span id="submitted-service">${service}</span></p>
    <p><strong>升级路径：</strong> <span id="submitted-route">${route}</span></p>
    <p><strong>摘要：</strong> <span id="submitted-summary">${summary}</span></p>
  `;
}
