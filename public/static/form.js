// Subida directa a R2: los bytes NO pasan por el Worker. Al enviar el form se
// pide una URL firmada (POST /upload-url), se sube cada archivo con PUT directo
// a R2, y luego se envia el form solo con metadata (key, nombre, tamano, dims).

const form = document.querySelector('form[action="/form"]');
const fileInput = document.getElementById('file');

// --- Preview + cards para el modo batch (varios archivos) -------------------
fileInput.addEventListener('change', function () {
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

// --- Subida directa a R2 al enviar ------------------------------------------

function readImageDimensions(file) {
    return new Promise((resolve) => {
        const url = URL.createObjectURL(file);
        const img = new Image();
        img.onload = () => {
            URL.revokeObjectURL(url);
            resolve({ width: img.naturalWidth, height: img.naturalHeight });
        };
        img.onerror = () => {
            URL.revokeObjectURL(url);
            resolve(null);
        };
        img.src = url;
    });
}

function addHidden(name, value) {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = name;
    input.value = value;
    input.className = 'uploaded-meta';
    form.appendChild(input);
}

form.addEventListener('submit', async (e) => {
    const files = Array.from(fileInput.files);

    // Sin archivo (posts): envio normal del form, nada que subir.
    if (files.length === 0) return;

    e.preventDefault();

    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn.textContent;
    btn.disabled = true;

    // Limpiar metadata de un intento previo (si el submit fallo antes).
    form.querySelectorAll('.uploaded-meta').forEach((el) => el.remove());

    const typeEl = form.querySelector('input[name="type"]:checked');
    const type = typeEl ? typeEl.value : null;

    try {
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            btn.textContent = `Subiendo ${i + 1}/${files.length}...`;

            // 1. Pedir URL firmada al Worker.
            const res = await fetch('/upload-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: file.name, content_type: file.type }),
            });
            if (!res.ok) throw new Error('No se pudo firmar la subida');
            const { key, url } = await res.json();

            // 2. PUT directo a R2 (los bytes no tocan el Worker).
            const put = await fetch(url, {
                method: 'PUT',
                headers: { 'Content-Type': file.type || 'application/octet-stream' },
                body: file,
            });
            if (!put.ok) throw new Error('Fallo la subida a R2');

            // 3. Dimensiones en el browser (solo fotos).
            let width = '';
            let height = '';
            if (type === 'photo') {
                const dims = await readImageDimensions(file);
                if (dims) {
                    width = dims.width;
                    height = dims.height;
                }
            }

            // 4. Metadata como hidden inputs (arrays paralelos, mismo orden).
            addHidden('file_keys', key);
            addHidden('file_names', file.name);
            addHidden('file_sizes', file.size);
            addHidden('widths', width);
            addHidden('heights', height);
        }

        form.submit();
    } catch (err) {
        btn.disabled = false;
        btn.textContent = originalText;
        alert('Error subiendo archivos: ' + err.message);
    }
});
