document.getElementById('file').addEventListener('change', function() {
    const files = Array.from(this.files);
    const container = document.getElementById('batch-cards');
    container.replaceChildren();

    if (files.length <= 1) return;

    files.forEach((file) => {
        const url = URL.createObjectURL(file);

        const card = document.createElement('div');
        card.style.cssText = 'border: 1px solid #ccc; padding: 1rem; margin-top: 1rem;';

        const img = document.createElement('img');
        img.src = url;  // object URL, no es HTML interpolado
        img.style.cssText = 'width: 100px; height: 100px; object-fit: cover;';
        card.appendChild(img);
        card.appendChild(document.createElement('br'));

        const titleLabel = document.createElement('label');
        titleLabel.textContent = 'Título';
        const titleInput = document.createElement('input');
        titleInput.type = 'text';
        titleInput.name = 'titles';
        titleInput.value = file.name;  // .value no parsea HTML
        card.appendChild(titleLabel);
        card.appendChild(document.createElement('br'));
        card.appendChild(titleInput);
        card.appendChild(document.createElement('br'));

        const descLabel = document.createElement('label');
        descLabel.textContent = 'Descripción';
        const descInput = document.createElement('input');
        descInput.type = 'text';
        descInput.name = 'descriptions';
        card.appendChild(descLabel);
        card.appendChild(document.createElement('br'));
        card.appendChild(descInput);
        card.appendChild(document.createElement('br'));

        const tagsLabel = document.createElement('label');
        tagsLabel.textContent = 'Tags propias';
        const tagsInput = document.createElement('input');
        tagsInput.type = 'text';
        tagsInput.name = 'photo_tags';
        card.appendChild(tagsLabel);
        card.appendChild(document.createElement('br'));
        card.appendChild(tagsInput);

        container.appendChild(card);
    });
});
