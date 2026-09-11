/* Keep each dashboard's actual device viewport; only scale its presentation. */
document.querySelectorAll('.viewport').forEach(viewport => {
    const frame = viewport.querySelector('iframe');
    const width = Number(frame.dataset.width);
    frame.style.width = `${width}px`;
    frame.style.height = `${Number(frame.dataset.height)}px`;
    const fit = () => { frame.style.transform = `scale(${viewport.clientWidth / width})`; };
    fit();
    if (typeof ResizeObserver === 'function') new ResizeObserver(fit).observe(viewport);
    else window.addEventListener('resize', fit);
});
