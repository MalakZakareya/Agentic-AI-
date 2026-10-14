
(() => {
  const THREE_URL =
    "https://cdn.jsdelivr.net/npm/three@0.160.1/build/three.module.js";

  async function startScene() {
    const container = document.getElementById("ai-3d-background");
    if (!container) return;

    const THREE = await import(THREE_URL);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      55,
      window.innerWidth / window.innerHeight,
      0.1,
      100
    );

    camera.position.z = 7;

    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true
    });

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    container.appendChild(renderer.domElement);

    const geometry = new THREE.TorusKnotGeometry(
      1.6, 0.45, 180, 24
    );

    const material = new THREE.MeshPhysicalMaterial({
      color: 0x8054ff,
      metalness: 0.55,
      roughness: 0.2,
      clearcoat: 1,
      clearcoatRoughness: 0.1
    });

    const object = new THREE.Mesh(geometry, material);
    scene.add(object);

    const purpleLight = new THREE.PointLight(0xa15cff, 80);
    purpleLight.position.set(3, 3, 4);
    scene.add(purpleLight);

    const blueLight = new THREE.PointLight(0x347bff, 65);
    blueLight.position.set(-3, -2, 3);
    scene.add(blueLight);

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));

    let mouseX = 0;
    let mouseY = 0;

    window.addEventListener("mousemove", (event) => {
      mouseX = (event.clientX / window.innerWidth - 0.5) * 0.6;
      mouseY = (event.clientY / window.innerHeight - 0.5) * 0.6;
    });

    const clock = new THREE.Clock();

    function animate() {
      requestAnimationFrame(animate);

      const time = clock.getElapsedTime();

      object.rotation.y += 0.003;
      object.rotation.x += 0.0015;
      object.position.y = Math.sin(time * 0.7) * 0.18;

      object.rotation.y +=
        (mouseX - object.rotation.y * 0.1) * 0.0005;

      object.rotation.x +=
        (mouseY - object.rotation.x * 0.1) * 0.0005;

      renderer.render(scene, camera);
    }

    animate();

    window.addEventListener("resize", () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    });
  }

  startScene().catch(console.error);
})();
