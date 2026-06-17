document.getElementById('file').addEventListener('change', function() {
    const files = Array.from(this.files);
    const container = document.getElementById('batch-cards');
    container.innerHTML = '';

    if (files.length <= 1) return;

    files.forEach((file) => {
        const url = URL.createObjectURL(file);
        container.innerHTML += `
            <div style="border: 1px solid #ccc; padding: 1rem; margin-top: 1rem;">
                <img src="${url}" style="width: 100px; height: 100px; object-fit: cover;">
                <br>
                <label>Título</label>
                <input type="text" name="titles" value="${file.name}">
                <br>
                <label>Descripción</label>
                <input type="text" name="descriptions">
                <br>
                <label>Tags propias</label>
                <input type="text" name="photo_tags">
            </div>
        `;
    });
});