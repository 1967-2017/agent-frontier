const form = document.querySelector('#intake-form');
const confirmation = document.querySelector('#confirmation');

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const requester = data.get('requester') || '未填写';
  const service = data.get('service') || '未填写';
  const route = data.get('route') || '未选择';
  const summary = data.get('summary') || '';
  const confirmationId = `INC-${new Date().toISOString().slice(0, 10).replaceAll('-', '')}-0427`;

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
});
