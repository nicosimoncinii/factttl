# Local engine and hardware

FactTTL uses the installed Ollama runtime with the local `qwen3:4b` GGUF model.
The standalone setup currently targets Windows x64 and PowerShell 7.4. Other
operating systems can use their own local Ollama installation; their installers
and hardware have not been validated here.

## Bounded profiles

| Profile | Context tokens | Source characters | Output tokens | Processing |
| --- | ---: | ---: | ---: | --- |
| cpu | 8192 | 2000 | 800 | Explicit CPU (`num_gpu: 0`) |
| balanced (default) | 8192 | 6000 | 1200 | Ollama hardware selection |
| extended | 32768 | 12000 | 1600 | Opt in; larger memory requirement |

Use `scripts/Start-FactTTL-Browser.ps1 -InferenceProfile cpu` for the CPU profile.
The choice persists in the ignored local configuration, without changing system
environment variables. An already running bridge requires restart to apply a
different profile. `scripts/Test-FactTTL-News.ps1` prints non-secret runtime and
hardware diagnostics and never downloads a model.

16 GB RAM is the recommended starting point for this model and other desktop
applications. An 8 GB computer is not a validated target; available memory, CPU
instructions, drivers, and other applications matter. No dedicated GPU is
required by the CPU profile. This does not imply acceptable speed on every CPU.
The setup also requires 10 GB free disk space during initial installation.

On the user's Windows PC, an explicit CPU-only `qwen3:4b` run with an 8192-token
context completed a synthetic date contradiction in 8.76 seconds including
7.11 seconds of model loading. The 11 generated JSON tokens took 0.74 seconds;
the result was `CONTRADICTED`. This is a short runtime smoke check, not a
benchmark of long articles, accuracy, or other computers. GPU acceleration is
not required for this measured case. The fixture disabled thinking with the
model's `/no_think` instruction in addition to the API setting.

The adapter rejects prompts exceeding its conservative UTF-8 byte budget rather
than silently losing evidence in the model context. A limited source excerpt
must remain labelled as limited evidence. A model result establishes consistency
with supplied evidence, not universal truth, and must pass citation validation.

The full adapter, including its JSON schema and validated citations, completed a
synthetic contradiction check on this PC in 30.53 seconds with GPU disabled.
Message analysis currently uses at most the first 1,500 source characters and
explicitly flags a longer source as an excerpt; the profile limits above are
upper bounds, not a promise to analyze the entire article.

Official references: [Ollama API](https://docs.ollama.com/api/chat),
[context and CPU/GPU reporting](https://docs.ollama.com/faq),
[runtime option definitions](https://github.com/ollama/ollama/blob/main/api/types.go).
