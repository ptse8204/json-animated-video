from __future__ import annotations

from motionjson import capabilities


def cuda_info(**overrides):
    base = {
        "torchInstalled": False,
        "torchVersion": None,
        "torchCudaBuild": None,
        "available": False,
        "cudaAvailable": False,
        "mpsAvailable": False,
        "mpsBuilt": False,
        "xpuAvailable": False,
        "hipVersion": None,
        "device": "cpu",
        "reasons": ["torch is not installed; CUDA status cannot be queried."],
        "devices": [{"name": "cpu", "available": True}],
    }
    base.update(overrides)
    return base


def fake_nvidia_gpu():
    return {
        "kind": "nvidia_cuda",
        "hardwareDetected": True,
        "visibleToTorch": False,
        "name": "NVIDIA T4",
        "memoryMb": 15360,
        "driver": "550.54",
        "source": "nvidia-smi",
    }


def test_runtime_environment_torch_missing_with_nvidia_smi_reports_runtime_missing(monkeypatch):
    monkeypatch.setattr(capabilities.platform, "system", lambda: "Linux")
    monkeypatch.setattr(capabilities.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(capabilities, "_nvidia_smi_accelerators", lambda: [fake_nvidia_gpu()])
    monkeypatch.setattr(capabilities, "_proc_nvidia_accelerator", lambda: None)
    monkeypatch.setattr(capabilities, "_env_hardware_accelerators", lambda: [])

    environment = capabilities.runtime_environment(cuda_info())

    assert environment["classification"] == "cuda_hardware_runtime_missing"
    assert environment["confidence"] == "high"
    assert "nvidia_hardware_detected" in environment["reasonCodes"]
    assert "torch_missing" in environment["reasonCodes"]
    assert "GPU detected" in " ".join(environment["messages"])
    assert environment["hardware"]["accelerators"][0]["name"] == "NVIDIA T4"
    assert environment["runtime"]["torchInstalled"] is False


def test_runtime_environment_torch_cpu_only_with_nvidia_hardware_reports_runtime_missing():
    environment = capabilities.runtime_environment(
        cuda_info(
            torchInstalled=True,
            torchVersion="2.7.0+cpu",
            reasons=["torch.cuda.is_available() returned false."],
        ),
        hardware_accelerators=[fake_nvidia_gpu()],
    )

    assert environment["classification"] == "cuda_hardware_runtime_missing"
    assert environment["runtime"]["torchInstalled"] is True
    assert environment["runtime"]["cudaAvailable"] is False
    assert "torch_cuda_unavailable" in environment["reasonCodes"]


def test_runtime_environment_torch_cuda_ready_reports_cuda_ready():
    environment = capabilities.runtime_environment(
        cuda_info(
            torchInstalled=True,
            torchVersion="2.7.0+cu124",
            torchCudaBuild="12.4",
            available=True,
            cudaAvailable=True,
            device="cuda",
            reasons=[],
            devices=[
                {"name": "cpu", "available": True},
                {"name": "cuda", "available": True, "deviceName": "NVIDIA L4"},
            ],
        ),
        hardware_accelerators=[],
    )

    assert environment["classification"] == "cuda_ready"
    assert environment["runtime"]["cudaAvailable"] is True
    assert environment["hardware"]["accelerators"][0]["visibleToTorch"] is True


def test_runtime_environment_apple_silicon_mps_ready(monkeypatch):
    monkeypatch.setattr(capabilities.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(capabilities.platform, "machine", lambda: "arm64")

    environment = capabilities.runtime_environment(
        cuda_info(
            torchInstalled=True,
            torchVersion="2.7.0",
            mpsAvailable=True,
            mpsBuilt=True,
            device="mps",
            reasons=[],
            devices=[{"name": "mps", "available": True}],
        ),
        hardware_accelerators=[],
    )

    assert environment["classification"] == "mps_ready"
    assert environment["runtime"]["mpsAvailable"] is True
    assert any(item["kind"] == "apple_mps" for item in environment["hardware"]["accelerators"])


def test_runtime_environment_apple_silicon_mps_runtime_missing(monkeypatch):
    monkeypatch.setattr(capabilities.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(capabilities.platform, "machine", lambda: "arm64")

    environment = capabilities.runtime_environment(
        cuda_info(torchInstalled=True, torchVersion="2.7.0+cpu"),
        hardware_accelerators=[],
    )

    assert environment["classification"] == "mps_hardware_runtime_missing"
    assert "torch_mps_unavailable" in environment["reasonCodes"]


def test_runtime_environment_without_accelerator_signals_reports_cpu_only(monkeypatch):
    monkeypatch.setattr(capabilities.platform, "system", lambda: "Linux")
    monkeypatch.setattr(capabilities.platform, "machine", lambda: "x86_64")

    environment = capabilities.runtime_environment(
        cuda_info(torchInstalled=True, torchVersion="2.7.0+cpu"),
        hardware_accelerators=[],
    )

    assert environment["classification"] == "cpu_only"
    assert environment["hardware"]["accelerators"][0]["kind"] == "cpu"
    assert environment["runtime"]["cudaAvailable"] is False
