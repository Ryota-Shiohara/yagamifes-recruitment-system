(() => {
  const bureauSelect = document.querySelector('[data-slots-url]');
  const availabilityList = document.querySelector('[data-availability-list]');
  if (!bureauSelect || !availabilityList) return;

  const showEmpty = (message) => {
    availabilityList.replaceChildren();
    const empty = document.createElement('p');
    empty.className = 'empty';
    empty.textContent = message;
    availabilityList.append(empty);
  };

  const renderSlots = (slots) => {
    availabilityList.replaceChildren();
    if (!slots.length) {
      showEmpty('この局の面接枠はありません。');
      return;
    }

    const list = document.createElement('div');
    list.className = 'checkbox-list';
    slots.forEach((slot) => {
      const label = document.createElement('label');
      label.className = 'checkbox-card';

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.name = 'availability_ids';
      checkbox.value = String(slot.id);
      checkbox.disabled = Boolean(slot.booked);

      const text = document.createElement('span');
      text.append(document.createTextNode(
        `${slot.start_at}〜${slot.end_at.slice(11)}`,
      ));
      if (slot.booked) {
        text.append(document.createElement('br'));
        const note = document.createElement('small');
        note.textContent = '予約済み';
        text.append(note);
      }

      label.append(checkbox, text);
      list.append(label);
    });
    availabilityList.append(list);
  };

  bureauSelect.addEventListener('change', async () => {
    const bureauId = bureauSelect.value;
    if (!bureauId) {
      showEmpty('希望局を選択すると面接枠が表示されます。');
      return;
    }

    const slotsUrl = new URL(
      bureauSelect.dataset.slotsUrl,
      window.location.href,
    );
    slotsUrl.searchParams.set('bureau_id', bureauId);
    bureauSelect.disabled = true;
    showEmpty('面接枠を読み込んでいます…');
    try {
      const response = await fetch(slotsUrl);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || '面接枠を読み込めませんでした。');
      }
      renderSlots(payload.slots || []);
    } catch (error) {
      showEmpty(error.message || '面接枠を読み込めませんでした。');
    } finally {
      bureauSelect.disabled = false;
    }
  });
})();
