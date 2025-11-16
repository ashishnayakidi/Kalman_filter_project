"""Local LFM2-350M runner using Ollama API (with fallback to local file)."""
import requests
from typing import Optional
from pathlib import Path
import os


class LocalLFM:
    """Wrapper for local LFM2-350M model via Ollama API or local GGUF file."""
    
    def __init__(self, model_name: Optional[str] = None, base_url: str = "http://localhost:11434", model_path: Optional[str] = None):
        """
        Initialize LFM model via Ollama or local file.
        
        Args:
            model_name: Ollama model name (e.g., "sam860/lfm2:350m")
            base_url: Ollama API base URL
            model_path: Path to local GGUF file (fallback if Ollama not available)
        """
        self.use_ollama = False
        self.model_name = model_name or os.getenv('OLLAMA_MODEL', 'sam860/lfm2:350m')
        self.base_url = base_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.api_url = f"{self.base_url}/api/generate"
        
        # If model_path is provided, it means we're using local file mode
        if model_path:
            # This is for backward compatibility - local file mode
            # We'll try Ollama first, then fall back to local file
            self._init_local_file(model_path)
        else:
            # Try Ollama first
            try:
                self._init_ollama()
            except Exception as e:
                print(f"Warning: Ollama initialization failed: {e}")
                raise
    
    def _init_ollama(self):
        """Initialize Ollama connection."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_found = any(m.get('name') == self.model_name for m in models)
                if not model_found:
                    available = [m.get('name') for m in models]
                    raise ValueError(f"Model '{self.model_name}' not found in Ollama. Available: {available}")
                self.use_ollama = True
                print(f"✓ Connected to Ollama, model '{self.model_name}' available")
            else:
                raise ConnectionError(f"Ollama API returned status {response.status_code}")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Could not connect to Ollama at {self.base_url}. Is Ollama running? Error: {e}")
    
    def _init_local_file(self, model_path: str):
        """Initialize local GGUF file (requires llama-cpp-python)."""
        try:
            from llama_cpp import Llama
            import platform
            
            model_path = Path(model_path)
            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found: {model_path}")
            
            is_mac = platform.system() == "Darwin"
            n_gpu_layers = 1 if is_mac else 0
            
            print(f"Loading local model from {model_path}...")
            self.llm = Llama(
                model_path=str(model_path),
                n_ctx=4096,
                n_gpu_layers=n_gpu_layers,
                verbose=False
            )
            self.use_ollama = False
            print("✓ Local model loaded successfully")
        except ImportError:
            raise ImportError("llama-cpp-python not installed. Install with: pip install llama-cpp-python")
        except Exception as e:
            raise RuntimeError(f"Failed to load local model: {e}")
    
    def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        """
        Generate text from prompt.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Generated text
        """
        if self.use_ollama:
            return self._generate_ollama(prompt, max_tokens, temperature)
        else:
            return self._generate_local(prompt, max_tokens, temperature)
    
    def _generate_ollama(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate using Ollama API."""
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "stop": []  # No stop sequences - let it generate fully
                }
            }
            
            response = requests.post(self.api_url, json=payload, timeout=180)
            response.raise_for_status()
            
            result = response.json()
            answer = result.get('response', '').strip()
            
            if not answer:
                # Check if there's an error in the response
                if 'error' in result:
                    raise RuntimeError(f"Ollama error: {result.get('error')}")
                # Sometimes response might be empty but done is True
                if result.get('done', False) and not answer:
                    raise RuntimeError("Ollama returned empty response")
            
            return answer
            
        except requests.exceptions.Timeout:
            raise RuntimeError("Ollama request timed out. The model may be taking too long to respond.")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error generating text with Ollama: {e}")
    
    def _generate_local(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate using local llama-cpp-python."""
        response = self.llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["\n\n\n", "---", "##"],
            echo=False
        )
        return response['choices'][0]['text'].strip()
