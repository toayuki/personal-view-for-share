// CSS を動的に挿入
const style = document.createElement('style');
style.textContent = `
  #particle-canvas {
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    pointer-events: none;
    z-index: 2;
  }
`;
document.head.appendChild(style);

// canvas を動的に挿入
const canvas = document.createElement('canvas');
canvas.id = 'particle-canvas';
document.body.prepend(canvas);

// Three.js を動的にロードしてから初期化
const script = document.createElement('script');
script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
script.onload = function () {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x000000, 0);

  function createCircleTexture() {
    const size = 64;
    const c = document.createElement('canvas');
    c.width = c.height = size;
    const ctx = c.getContext('2d');
    const g = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, size/2);
    g.addColorStop(0,   'rgba(255,255,255,1)');
    g.addColorStop(0.2, 'rgba(255,255,255,0.8)');
    g.addColorStop(0.4, 'rgba(255,255,255,0.4)');
    g.addColorStop(1,   'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
    return new THREE.CanvasTexture(c);
  }

  const count = 200;
  const positions  = new Float32Array(count * 3);
  const colors     = new Float32Array(count * 3);
  const phases     = new Float32Array(count);
  const speeds     = new Float32Array(count);
  const amplitudes = new Float32Array(count);
  const fadeStartY = new Float32Array(count);

  function randomFadeStart() { return -100 + Math.random() * 200; }

  for (let i = 0; i < count; i++) {
    positions[i*3]   = (Math.random() - 0.5) * 400;
    positions[i*3+1] = Math.random() * 400 - 200;
    positions[i*3+2] = (Math.random() - 0.5) * 400;
    phases[i]      = Math.random() * Math.PI * 2;
    speeds[i]      = 0.5 + Math.random() * 0.5;
    amplitudes[i]  = 2 + Math.random() * 4;
    fadeStartY[i]  = randomFadeStart();
    colors[i*3] = colors[i*3+1] = colors[i*3+2] = 1;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    map: createCircleTexture(),
    size: 2,
    transparent: true,
    opacity: 0.9,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexColors: true
  });

  scene.add(new THREE.Points(geometry, material));
  camera.position.z = 200;

  (function animate() {
    requestAnimationFrame(animate);
    const time = Date.now() * 0.002;
    const pos = geometry.attributes.position.array;
    const col = geometry.attributes.color.array;
    for (let i = 0; i < count; i++) {
      pos[i*3+1] += speeds[i];
      pos[i*3]   += Math.sin(time + phases[i]) * amplitudes[i] * 0.1;

      const y = pos[i*3+1];
      const fs = fadeStartY[i];
      const brightness = y < fs ? 1 : Math.max(0, 1 - (y - fs) / (200 - fs));
      col[i*3] = col[i*3+1] = col[i*3+2] = brightness;

      if (y > 200) {
        pos[i*3+1] = -200;
        pos[i*3]   = (Math.random() - 0.5) * 400;
        pos[i*3+2] = (Math.random() - 0.5) * 400;
        phases[i]     = Math.random() * Math.PI * 2;
        fadeStartY[i] = randomFadeStart();
        col[i*3] = col[i*3+1] = col[i*3+2] = 1;
      }
    }
    geometry.attributes.position.needsUpdate = true;
    geometry.attributes.color.needsUpdate = true;
    renderer.render(scene, camera);
  })();

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });
};
document.head.appendChild(script);
