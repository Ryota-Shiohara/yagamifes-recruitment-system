(() => {
  const board = document.querySelector('[data-assignment-board]');
  if (!board) return;

  const status = board.querySelector('[data-assignment-status]');
  let draggedApplicantId = null;

  const cards = () => Array.from(
    board.querySelectorAll('[data-applicant-id]'),
  );
  const zones = () => Array.from(
    board.querySelectorAll('[data-slot-id]'),
  );

  const setStatus = (message, isError = false) => {
    status.hidden = !message;
    status.textContent = message;
    status.classList.toggle('error', isError);
    status.classList.toggle('success', !isError && Boolean(message));
  };

  const cardFor = (applicantId) => cards().find(
    (card) => card.dataset.applicantId === applicantId,
  );

  const canDrop = (zone, card) => {
    const slotId = zone.dataset.slotId;
    const availabilityIds = (card.dataset.availabilityIds || '')
      .split(',')
      .filter(Boolean);
    if (slotId && !availabilityIds.includes(slotId)) {
      return 'この応募者が希望していない面接枠です。';
    }
    const occupiedApplicantId = zone.dataset.occupiedApplicantId;
    if (
      occupiedApplicantId
      && occupiedApplicantId !== card.dataset.applicantId
    ) {
      return 'この面接枠はすでに予約されています。';
    }
    return '';
  };

  const clearZoneState = () => zones().forEach((zone) => {
    zone.classList.remove('is-dragover', 'is-invalid-drop');
  });

  cards().forEach((card) => {
    if (card.getAttribute('draggable') === 'false') return;
    card.addEventListener('dragstart', (event) => {
      draggedApplicantId = card.dataset.applicantId;
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', draggedApplicantId);
      card.classList.add('is-dragging');
    });
    card.addEventListener('dragend', () => {
      draggedApplicantId = null;
      card.classList.remove('is-dragging');
      clearZoneState();
    });
  });

  zones().forEach((zone) => {
    zone.addEventListener('dragover', (event) => {
      const applicantId = draggedApplicantId
        || event.dataTransfer.getData('text/plain');
      const card = cardFor(applicantId);
      if (!card) return;
      const reason = canDrop(zone, card);
      clearZoneState();
      if (reason) {
        zone.classList.add('is-invalid-drop');
        event.dataTransfer.dropEffect = 'none';
        return;
      }
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      zone.classList.add('is-dragover');
    });

    zone.addEventListener('dragleave', () => {
      zone.classList.remove('is-dragover', 'is-invalid-drop');
    });

    zone.addEventListener('drop', async (event) => {
      event.preventDefault();
      const applicantId = draggedApplicantId
        || event.dataTransfer.getData('text/plain');
      const card = cardFor(applicantId);
      if (!card) return;
      const reason = canDrop(zone, card);
      clearZoneState();
      if (reason) {
        setStatus(reason, true);
        return;
      }

      setStatus('面接枠を更新しています。');
      const body = new URLSearchParams({
        applicant_id: applicantId,
        bureau_schedule_id: zone.dataset.slotId,
      });
      try {
        const response = await fetch(board.dataset.assignmentUrl, {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          body,
        });
        const payload = await response.json();
        if (!response.ok || !payload.success) {
          throw new Error(payload.error || '面接枠を更新できませんでした。');
        }
        window.location.reload();
      } catch (error) {
        setStatus(error.message, true);
      }
    });
  });
})();
