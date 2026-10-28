(function () {
  "use strict";

  const statusCopy = {
    neutral: { title: "Esperando la cámara", message: "La cámara no se activa hasta que hagas clic en “Iniciar cámara”.", icon: "i" },
    ready: { title: "Cámara lista", message: "Podés capturar un frame para registrar la asistencia.", icon: "✓" },
    progress: { title: "Captura en progreso", message: "Analizando el frame. Esperá un momento…", icon: "…" },
    unavailable: { title: "Cámara no disponible", message: "No se pudo acceder a la cámara. Revisá los permisos del navegador y que ningún otro programa la esté usando.", icon: "!" },
    unknown: { title: "Rostro no reconocido", message: "No encontramos un empleado registrado en la captura. Probá con mejor iluminación.", icon: "?" },
    multiple: { title: "Hay varios rostros", message: "La captura debe contener exactamente un rostro. Volvé a intentarlo sin otras personas en cuadro.", icon: "!" },
    registered: { title: "Asistencia registrada", message: "La marcación se guardó correctamente en el registro.", icon: "✓" },
    duplicate: { title: "Marcación duplicada", message: "Ese empleado ya tiene una marcación del mismo tipo para hoy.", icon: "↺" },
    error: { title: "No se pudo completar la captura", message: "Revisá la cámara y volvé a intentar.", icon: "!" }
  };

  function setStatus(panel, state, detail) {
    const copy = statusCopy[state] || statusCopy.error;
    panel.className = "status-panel status-panel--" + state;
    panel.querySelector("[data-status-title]").textContent = copy.title;
    panel.querySelector("[data-status-message]").textContent = copy.message;
    panel.querySelector("[data-status-icon]").textContent = copy.icon;
    panel.querySelector("[data-recognition-detail]").textContent = detail || "";
  }

  function getRecognitionState(payload) {
    const status = String(payload && payload.status || "error").toLowerCase();
    if (status.includes("duplicate") || status.includes("duplic") || status.includes("ya_registr")) return "duplicate";
    if (status.includes("multiple") || status.includes("varios") || status.includes("muchos")) return "multiple";
    if (status.includes("unknown") || status.includes("desconoc") || status.includes("no_match") || status.includes("no_face")) return "unknown";
    if (status.includes("registered") || status.includes("registr") || status === "ok" || status === "success") return "registered";
    if (status.includes("camera") || status.includes("unavailable")) return "unavailable";
    return "error";
  }

  function employeeLabel(employee) {
    if (!employee) return "";
    if (typeof employee === "string") return employee;
    return employee.name || employee.nombre || employee.id || employee.id_empleado || "Empleado reconocido";
  }

  function detailFromPayload(payload) {
    const parts = [];
    const name = employeeLabel(payload && payload.employee);
    if (name) parts.push(name);
    if (payload && payload.distance !== undefined && payload.distance !== null) {
      const distance = Number(payload.distance);
      if (Number.isFinite(distance)) parts.push("Distancia facial: " + distance.toFixed(4));
    }
    return parts.join(" · ");
  }

  function setupCamera() {
    const root = document.querySelector("[data-camera-app]");
    if (!root) return;

    const video = root.querySelector("[data-camera-video]");
    const canvas = root.querySelector("[data-camera-canvas]");
    const placeholder = root.querySelector("[data-camera-placeholder]");
    const startButton = root.querySelector("[data-start-camera]");
    const stopButton = root.querySelector("[data-stop-camera]");
    const captureButton = root.querySelector("[data-capture]");
    const eventType = root.querySelector("[data-event-type]");
    const statusPanel = root.querySelector("[data-status-panel]");
    let stream = null;

    function stopCamera() {
      if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
      stream = null;
      video.srcObject = null;
      video.hidden = true;
      placeholder.hidden = false;
      startButton.disabled = false;
      stopButton.disabled = true;
      captureButton.disabled = true;
      setStatus(statusPanel, "neutral");
    }

    async function startCamera() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setStatus(statusPanel, "unavailable");
        return;
      }

      startButton.disabled = true;
      setStatus(statusPanel, "progress", "Solicitando permiso de cámara…");
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
        video.srcObject = stream;
        video.hidden = false;
        placeholder.hidden = true;
        await video.play();
        stopButton.disabled = false;
        captureButton.disabled = false;
        setStatus(statusPanel, "ready");
      } catch (error) {
        if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
        stream = null;
        startButton.disabled = false;
        stopButton.disabled = true;
        captureButton.disabled = true;
        setStatus(statusPanel, "unavailable", error && error.name === "NotAllowedError" ? "El permiso de cámara fue rechazado." : "El dispositivo no informó una cámara utilizable.");
      }
    }

    async function captureFrame() {
      if (!stream || !video.videoWidth || !video.videoHeight) {
        setStatus(statusPanel, "unavailable");
        return;
      }

      captureButton.disabled = true;
      setStatus(statusPanel, "progress");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);

      canvas.toBlob(async function (blob) {
        if (!blob) {
          captureButton.disabled = false;
          setStatus(statusPanel, "error", "El navegador no pudo preparar la imagen.");
          return;
        }

        const formData = new FormData();
        formData.append("event_type", eventType.value);
        formData.append("frame", blob, "capture.jpg");
        try {
          const response = await fetch("/api/attendance/recognize", { method: "POST", body: formData, headers: { Accept: "application/json" } });
          const payload = await response.json();
          const state = getRecognitionState(payload);
          const detail = detailFromPayload(payload);
          if (!response.ok && state === "error") setStatus(statusPanel, "error", payload.message || "El servidor rechazó la captura.");
          else setStatus(statusPanel, state, detail);
        } catch (error) {
          setStatus(statusPanel, "error", "No se pudo conectar con el servicio de reconocimiento.");
        } finally {
          captureButton.disabled = false;
        }
      }, "image/jpeg", 0.9);
    }

    video.hidden = true;
    placeholder.hidden = false;
    startButton.addEventListener("click", startCamera);
    stopButton.addEventListener("click", stopCamera);
    captureButton.addEventListener("click", captureFrame);
    window.addEventListener("beforeunload", stopCamera);
  }

  function setupDeleteConfirmation() {
    document.querySelectorAll("[data-delete-form]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        const name = form.dataset.employeeName || "este empleado";
        if (!window.confirm("¿Querés eliminar la imagen de " + name + "? Los registros históricos se conservarán.")) event.preventDefault();
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupCamera();
    setupDeleteConfirmation();
  });
}());
