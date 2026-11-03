# yjcli 재구성 기획 (v1.0)

> 상태: 구현 완료 (0.3.0) · 기준 버전: 0.2.5 · 작성일: 2026-11-03
>
> 구현하면서 바뀐 세부 사항은 §12 에 정리했다.
>
> 기존 0.2.x 로 만든 저장소는 모두 새로 구성한다. **마이그레이션과 하위 호환은 고려하지 않는다.**

## 1. 배경과 목표

### 현재 구조의 문제

| 문제 | 현재 동작 |
|------|-----------|
| 명령이 흩어져 있음 | `init` / `platform add` / `service add` / `sync agents·skills·make·all·migrate` 를 상황별로 골라 써야 함 |
| LLM 선택 불가 | Cursor·Claude·Codex 3종을 항상 전부 설치 (`.cursor/`, `.claude/`, `.agents/`) |
| 스킬이 플랫폼과 무관하게 설치됨 | 선택한 플랫폼과 상관없이 패키지의 스킬 9종을 전부 설치. `sync migrate` 는 스킬 디렉터리를 통째로 지워서 사용자가 직접 만든 스킬도 사라짐 |
| 코드와 도구가 섞여 있음 | 플랫폼 폴더에 `scripts/`(run/build/deploy), 서비스 폴더에 환경별 `.env.*` 와 `Dockerfile` 이 함께 생성됨. 코드만 필요한 경우에도 전부 따라옴 |
| 빌드 플러그인이 플랫폼마다 복사됨 | `plugin-build-*.sh` 가 모든 플랫폼의 `scripts/` 에 복사되고, 서비스 보일러플레이트 플러그인(`_SERVICE_BOILERPLATE_PLUGINS`)은 또 따로 정의됨 |
| 플랫폼 이름이 성격을 드러내지 못함 | `backend` 가 MSA, `backend-service` 가 단일 백엔드. `backend-service` 하나에 SSR·gRPC 옵션이 섞여 있음 |
| 스킬과 플랫폼 이름이 하드코딩으로 얽힘 | 스킬 본문·description·`AGENTS.md` 라우팅 표에 다른 플랫폼 이름이 직접 적혀 있어, 플랫폼을 바꾸면 여러 파일을 손으로 고쳐야 함 |
| 플랫폼과 서비스 생성이 분리됨 | `init` 으로 플랫폼을 만든 뒤 `service add -p … -n …` 를 서비스마다 한 번씩 실행해야 함 |
| 신규/업데이트 경계가 모호 | `init --force`, `sync all`, `sync migrate` 가 각자 다른 덮어쓰기 규칙을 가짐 |
| 상태를 기억하지 않음 | 무엇을 선택해 설치했는지 저장하지 않아 업데이트 때 다시 추론하거나 다시 물어봐야 함 |
| 실행 중에 파일을 씀 | 질문과 쓰기가 섞여 있어 중간에 취소하면 반쯤 적용된 상태가 남음 |

### 목표

1. **`yjcli` 하나로 시작** — 인자 없이 실행하면 단계별 체크리스트(위저드)를 띄운다.
2. **모든 선택은 마지막에 한 번에 적용** — 질문 단계에서는 파일을 쓰지 않는다. 계획을 요약해 보여주고, 확인을 받은 뒤 실행한다.
3. **파라미터가 곧 답변** — 인자로 준 항목은 해당 단계를 건너뛴다. 모든 단계를 인자로 채우면 완전 비대화형이 된다.
4. **플랫폼·서비스는 코드만, 나머지는 플러그인** — 플랫폼과 서비스를 만들 때는 순수하게 코드 관련 내용만 넣는다. 실행·환경 파일·빌드/배포 같은 도구는 저장소 단위 **플러그인**(`runner`, `secrets`, `builder`)으로 분리해 `tools/` 아래에 둔다.
5. **고르는 것은 LLM · 플랫폼 · 플러그인** — 모두 다중 선택. 스킬은 플랫폼(과 플러그인)에 따라 자동으로 정해진다.
6. **플랫폼과 서비스 이름을 한 흐름에서** — 플랫폼마다 서비스 이름을 여러 개 입력받아 `<platform>/<name>` 을 한 번에 만든다.
7. **신규 설치와 업데이트를 같은 흐름으로** — 저장된 선택(매니페스트)이 있으면 업데이트 모드로 들어간다.
8. **플랫폼 체계와 스킬 연동을 다시 짠다** — 플랫폼 9종으로 재편하고, 스킬은 카탈로그를 기준으로 렌더링한다.

### 용어

| 용어 | 뜻 |
|------|----|
| 플랫폼 | 저장소 루트의 코드 폴더 종류 (`backend`, `frontend` …) |
| 서비스 | 플랫폼 아래의 앱 하나 (`backend/a1`) |
| 플랫폼 옵션 | 플랫폼이 선언한 코드 관련 선택지. 현재는 `proto` 하나 |
| **플러그인** | 저장소 단위 도구. `tools/` 아래에 설치된다 (`runner`, `secrets`, `builder`). 0.2.x 의 `plugin-build-*.sh` (플랫폼 빌드 플러그인)와는 다른 개념이다 |
| 빌드 단계 | 0.2.x 의 `plugin-build-*.sh`. `builder` 플러그인 안의 `steps/` 로 옮긴다 (§4.4) |

### 범위 밖

- 0.2.x 저장소 마이그레이션, 기존 명령(`init` / `platform` / `sync`) 별칭.
- `Diff.md` (0.2.x 에서 마이그레이션 차이를 적던 사용자 메모). 마이그레이션이 없으므로 **만들지 않고 템플릿도 삭제**한다. `AGENTS.md` 템플릿에서 `Diff.md` 를 언급하는 부분(저장소 구조 표, 차이 기록 규칙 절, 문서 위치 표)도 함께 지운다.
- `TOOLS.md` (릴리스 도구 명세: version / deploy / git). **만들지 않고 템플릿도 삭제**한다. `AGENTS.md` 템플릿의 저장소 구조 표와 문서 위치 표에서도 지운다.
- 실행·빌드·배포 스크립트의 **동작 원리**(플랫폼 단위 실행, 서비스별 `RUN_COMMAND`, 빌드 단계의 폴더 유무 감지, 구현 전까지 실패하는 가드 스텁)는 유지한다. 위치와 경로만 `tools/` 기준으로 바뀐다.
- 스킬의 아키텍처 규칙 자체(레이어, 역할, import 규칙)는 바꾸지 않는다. 플랫폼 재편·플러그인 분리에 따른 분리·이름 변경·참조 정리만 한다 (§5).

---

## 2. 사용자 흐름

### 2.1 전체 흐름

```
yjcli
  │
  ├─ 0. 상태 감지 ── .yjcli/manifest.toml 있음? ──┬─ 없음 → 신규(new)
  │                                               └─ 있음 → 업데이트(update)
  │
  ├─ 1. LLM 대상        [다중]  Cursor / Claude Code / Codex / …
  ├─ 2. 플랫폼          [다중]  space 로 [x] 표시, 여러 개 선택
  ├─ 3. 플러그인        [다중]  runner / secrets / builder
  ├─ 4. 서비스 이름     [플랫폼마다 한 화면]
  │      ├─ backend 이름:  a1, a2      (공백 또는 , 로 구분)
  │      │    └─ backend 플랫폼 옵션 (있는 플랫폼만: proto)
  │      └─ frontend 이름: f1
  │
  ├─ 5. 계획 요약 ── 생성 / 덮어쓰기 / 보존 / 삭제 파일 목록
  │        └─ 확인 [Y/n/back]
  │
  └─ 6. 실행 → 코드(backend/a1, backend/a2, frontend/f1) + 플러그인(tools/…) 생성 → 매니페스트 저장
```

스킬은 묻지 않는다. 선택한 플랫폼과 플러그인으로 자동 결정된다 (§5.4).

### 2.2 화면 예시

**2단계 — 플랫폼 선택**

```
yjcli 0.3.0 · /path/to/repo · 신규 설치

  ✔ 1. LLM 대상        Cursor, Claude Code
  ▸ 2. 플랫폼
  ○ 3. 플러그인
  ○ 4. 서비스 이름
  ○ 5. 확인 및 실행

? 플랫폼을 선택하세요 (space: 선택/해제, a: 전체, enter: 다음, ←: 이전)
    [x] backend            단일 백엔드 (API)
    [ ] backend-msa        gRPC MSA
    [ ] backend-ssr        서버 템플릿/SSR
  > [x] frontend           Vite + React + TS
    [ ] mobile-app         Flutter
    [ ] pc-app             Electron
    [ ] cli
    [ ] browser-extension  MV3
    [ ] scheduler
```

- `space` 로 현재 줄을 `[x]` / `[ ]` 로 바꾼다. 위아래 화살표로 이동하고 `enter` 로 다음 단계로 넘어간다.
- 하나도 고르지 않고 `enter` 를 누르면 "최소 1개를 선택하세요"를 보여주고 그대로 머문다.
- 화면에 보이는 순서(카탈로그 순서)가 4단계에서 이름을 묻는 순서다.

**3단계 — 플러그인 선택**

```
  ✔ 2. 플랫폼          backend, frontend
  ▸ 3. 플러그인

? 플러그인을 선택하세요 (space: 선택/해제, enter: 다음, ←: 이전)
    [x] runner    플랫폼 일괄 실행 + Makefile        tools/runner/   (secrets 필요)
    [x] secrets   서비스별 환경 파일 모음 (평문 커밋)  tools/secrets/
    [ ] builder   빌드/배포 스크립트 + Dockerfile      tools/builder/  (secrets 필요)
```

- 의존 관계가 있는 플러그인은 함께 움직인다. `runner` 를 체크하면 `secrets` 도 자동으로 체크되고, `secrets` 를 해제하면 그것을 필요로 하는 `runner`·`builder` 도 해제된다. 바뀐 내용은 화면 아래에 한 줄로 알려준다 (`runner 는 secrets 가 필요해 함께 선택했습니다`).
- 플러그인을 하나도 고르지 않아도 된다. 그러면 코드와 에이전트 설정만 만든다.

**4단계 — 플랫폼별 서비스 이름 (backend → frontend 순서)**

```
  ✔ 3. 플러그인        runner, secrets
  ▸ 4. 서비스 이름     (1/2) backend

? backend 서비스 이름 (공백 또는 , 로 구분): a1, a2
  → backend/a1, backend/a2

? backend 플랫폼 옵션
    [ ] proto    gRPC/protobuf 사용 (backend/proto/ 생성)
```

```
  ▸ 4. 서비스 이름     (2/2) frontend

? frontend 서비스 이름 (공백 또는 , 로 구분): f1
  → frontend/f1
```

- 플랫폼 옵션이 없는 플랫폼(`frontend`, `cli` 등)은 이름만 묻는다.
- 입력 직후 `→ backend/a1, backend/a2` 처럼 만들어질 경로를 보여준다.

**공통**

- 위쪽 체크리스트에 끝난 단계(✔)와 현재 단계(▸)를 계속 보여준다.
- `←` 또는 `back` 으로 이전 화면으로 돌아갈 수 있다 (4단계 안에서는 이전 플랫폼으로). 2단계에서 플랫폼을 빼면 그 플랫폼에 입력한 이름은 버리고, 새로 넣은 플랫폼만 4단계에서 이름을 묻는다.
- 인자로 채운 단계는 `✔ 1. LLM 대상  Cursor (--llm)` 처럼 출처를 표시하고 건너뛴다.

### 2.3 서비스 이름 입력 규칙

| 규칙 | 내용 |
|------|------|
| 구분자 | 공백과 `,` 를 모두 허용하고 섞어 써도 된다. `a1,a2` · `a1 a2` · `a1, a2` 는 모두 `[a1, a2]` |
| 빈 항목 | `a1,,a2` 나 앞뒤 공백은 무시한다 |
| 개수 | 신규 플랫폼은 **최소 1개**. 비우고 `enter` 를 누르면 다시 묻는다 |
| 이름 형식 | `^[A-Za-z0-9_][A-Za-z0-9_-]*$` (현재와 같음) |
| 예약어 | `proto` 는 쓸 수 없다 (플랫폼 옵션 폴더) |
| 중복 | 같은 입력 안에서 중복되면 한 번만 쓰고 알려준다. 이미 있는 폴더와 겹치면 오류 |
| 잘못된 항목 | 어떤 항목이 왜 잘못되었는지 보여주고 **같은 플랫폼의 입력 화면을 다시** 띄운다. 이전 입력을 기본값으로 채워 둔다 |
| 이름별 변형 | `browser-extension` 에서 `native_` 로 시작하는 이름은 native host 구조로 만든다 (§4.2) |

> 플랫폼 폴더에 `scripts/` 가 없어졌으므로 예약어에서 `scripts` 를 뺀다.

### 2.4 계획 요약 (5단계)

```
계획 요약 — 신규 설치
┌────────────┬──────────────────────────────────────────────┐
│ LLM        │ cursor, claude                               │
│ 플랫폼     │ backend, frontend                            │
│ 플러그인   │ runner, secrets                              │
│ 서비스     │ backend/a1, backend/a2, frontend/f1          │
│ 스킬(자동) │ yj-arch-core, yj-backend, yj-frontend        │
└────────────┴──────────────────────────────────────────────┘
  + 생성     41개
  ~ 덮어쓰기  0개
  = 보존      0개
  - 삭제      0개
  (자세히 보기: d)

  ! secrets: tools/secrets/ 는 평문으로 커밋됩니다. private 저장소에서만 사용하세요.

? 적용할까요? [Y/n/back/d]
```

업데이트 모드에서는 `~ 덮어쓰기` 와 `- 삭제` 를 파일 단위로 펼쳐서 보여준다. 사용자가 고친 파일은 `!` 로 표시한다 (§6.3).

### 2.5 생성 결과 예

`backend`(a1, a2) + `frontend`(f1), 플러그인 `runner` + `secrets` + `builder`, LLM `claude`:

```
repo/
├── AGENTS.md  CLAUDE.md  .gitignore
├── .claude/{settings.json, skills/yj-*}
├── .yjcli/manifest.toml
│
├── backend/                          ← 코드 (+ builder 의 Dockerfile)
│   ├── a1/{apps,services,domains,modules}/  .env.examples  Dockerfile  .dockerignore
│   └── a2/{apps,services,domains,modules}/  .env.examples  Dockerfile  .dockerignore
├── frontend/
│   └── f1/src/  package.json  vite.config.ts  .env.examples  Dockerfile  .dockerignore
│
├── Makefile  make.bat                ← runner (+ builder 타깃)
└── tools/
    ├── runner/run.sh  run.bat  run.ps1                       ← runner
    ├── secrets/                                              ← secrets
    │   ├── backend/a1/.env.local-dev  .env.development  .env.production
    │   ├── backend/a2/…
    │   └── frontend/f1/…
    └── builder/                                              ← builder
        ├── build-common.sh  deploy-common.sh
        ├── steps/proto.sh  ssr.sh  docker.sh
        ├── backend/build-development.sh  build-production.sh  deploy-development.sh  deploy-production.sh
        └── frontend/…
```

> `Dockerfile` 은 Docker 빌드 컨텍스트에 맞춰 서비스 폴더에 둔다 (D15). "서비스 폴더는 코드만" 원칙의 유일한 예외이며, `builder` 를 고른 경우에만 생긴다.

### 2.6 업데이트 모드에서의 차이

| 단계 | 동작 |
|------|------|
| 2. 플랫폼 | 매니페스트의 플랫폼이 `[x]` 로 미리 선택되어 있다. 서비스가 있는 플랫폼은 `[x] backend (서비스 2개)` 로 표시하고 해제할 수 없다 |
| 3. 플러그인 | 매니페스트의 플러그인이 미리 선택되어 있다. 새로 체크하면 기존 서비스 전체에 대해 설치되고, 해제하면 관리 파일만 지운다 (§6.3) |
| 4. 서비스 이름 | 기존 서비스를 `기존: a1, a2` 로 보여주고, 입력한 이름은 **추가**된다. 기존 플랫폼은 비워 둬도 된다 (추가 없음). 새로 고른 플랫폼은 최소 1개 |

서비스 삭제는 yjcli 가 하지 않는다. 폴더를 지우면 다음 실행 때 매니페스트에서 정리된다.

---

## 3. 명령 체계

### 3.1 명령

| 명령 | 역할 |
|------|------|
| `yjcli` | 위저드. 상태를 감지해 신규 또는 업데이트로 진행 |
| `yjcli --yes` | 매니페스트(또는 인자)대로 바로 적용. 업데이트 자동화와 CI용 |
| `yjcli plan` | 실행하지 않고 계획만 출력 (`--dry-run` 과 같음) |
| `yjcli service add` | 업데이트 모드에서 4단계(서비스 이름)만 실행. 예: `yjcli service add -n backend=a3` |
| `yjcli status` | 매니페스트 내용 + 패키지 버전 차이 + 사용자가 수정한 관리 파일 목록 |
| `yjcli doctor` | 패키지에 포함된 자산 점검 |

기존 `init` / `platform add` / `sync *` 는 제거한다. 별칭을 두지 않는다.

### 3.2 공통 파라미터 (단계 건너뛰기)

| 파라미터 | 채우는 단계 | 예 |
|----------|-------------|----|
| `--llm` / `-l` | 1. LLM | `--llm cursor,claude` · `--llm all` |
| `--platform` / `-p` | 2. 플랫폼 | `-p backend -p frontend` · `-p backend,frontend` · `-p all` |
| `--plugin` | 3. 플러그인 | `--plugin runner,secrets` · `--plugin all` · `--plugin none` |
| `--name` / `-n` | 4. 서비스 이름 | `-n backend=a1,a2 -n frontend=f1` · `-n "backend=a1 a2"` |
| `--option` / `-o` | 4. 플랫폼 옵션 | `-o backend=proto` |
| `--mode` | 0. 상태 | `new` / `update` (자동 감지 결과를 덮어씀) |
| `--yes` / `-y` | 5. 확인 | 확인 없이 실행 |
| `--dry-run` | 5. 확인 | 계획만 출력하고 종료 |
| `--path` | — | 대상 저장소 루트 |
| `--force` | — | 사용자가 수정한 관리 파일도 덮어씀 (§6.3) |

규칙:

- 여러 값을 받는 인자는 반복 지정과 쉼표 구분을 모두 허용한다. `--name` 의 이름 목록은 위저드와 같은 규칙(§2.3)으로 공백도 허용한다 (셸에서는 따옴표 필요).
- `-n backend=…` 만 주고 `-p` 를 생략하면 `backend` 는 선택된 것으로 본다.
- `--plugin runner` 처럼 의존 플러그인을 빠뜨리면 자동으로 추가하고 한 줄로 알린다 (`secrets 를 함께 추가했습니다`).
- 업데이트 모드에서 인자를 생략한 단계는 **매니페스트 값을 기본 선택으로 보여준다**. `--yes` 와 함께 쓰면 매니페스트 값을 그대로 쓴다.
- stdin 이 TTY 가 아닌데 비어 있는 단계가 있으면 (예: 신규 플랫폼인데 `-n` 이 없음, `--plugin` 이 없음), 어떤 인자가 빠졌는지 한 번에 모두 알려주고 종료한다.

예: `yjcli -l claude -n backend=a1,a2 -n frontend=f1 --plugin runner -y`

---

## 4. 카탈로그 설계 (LLM · 플랫폼 · 플러그인)

선택 항목은 모두 **선언형 카탈로그**로 정의한다. 지금 `scaffold.py` 의 `if platform == …` 분기와 `_PLATFORM_SCRIPT_NAMES` 같은 하드코딩 목록을 카탈로그 데이터로 옮긴다. 새 LLM, 플랫폼, 플러그인, 스킬을 추가할 때 카탈로그 항목 하나와 템플릿만 더하면 되도록 하는 것이 목표다. 스킬은 §5 에서 따로 다룬다.

### 4.1 LLM 어댑터

| id | 표시 이름 | 설치 파일 |
|----|-----------|-----------|
| `cursor` | Cursor | `AGENTS.md`, `.cursor/skills/*` |
| `claude` | Claude Code | `CLAUDE.md`, `.claude/skills/*`, `.claude/settings.json` |
| `codex` | Codex | `AGENTS.md`, `.agents/skills/*` |
| (확장) `gemini` | Gemini CLI | `GEMINI.md` |
| (확장) `copilot` | GitHub Copilot | `.github/copilot-instructions.md` |

첫 릴리스는 `cursor` · `claude` · `codex` 3종만 제공하고, 확장 LLM 은 어댑터 구조만 준비한다 (D5).

- `AGENTS.md` 는 공통 원본이다. 어떤 LLM을 고르든 항상 설치한다.
- 각 어댑터는 "지침 파일 1개 + 스킬 디렉터리 + 기타 설정"을 선언한다.
- 지침 파일은 **import 방식**으로 만든다 (D1). `CLAUDE.md` 에는 `@AGENTS.md` 한 줄만 두고, Claude Code 가 실행할 때 `AGENTS.md` 를 불러온다. 복사본을 맞추는 동기화 단계(구 `sync agents`)는 없다. Cursor·Codex 는 `AGENTS.md` 를 직접 읽는다.
- `AGENTS.md` 의 스킬 설치 위치와 저장소 구조 표는 선택한 LLM만 나오도록 렌더링한다 (§4.6).

```python
# catalog/llms.py (예시)
LLM(
    id="claude",
    label="Claude Code",
    instructions=Instructions(path="CLAUDE.md", mode="import"),   # 내용: @AGENTS.md
    skills_dir=".claude/skills",
    extras=(Managed("settings.json", dest=".claude/settings.json", policy="seed"),),
)
```

### 4.2 플랫폼 (코드만)

플랫폼과 서비스를 만들 때는 **코드 관련 내용만** 만든다. 플랫폼 폴더에는 서비스 폴더(와 옵션인 `proto/`)만 있고, 서비스 폴더에는 코드 폴더·스택 기본 파일·`.env.examples` 만 있다.

| 만드는 것 (플랫폼) | 만들지 않는 것 (→ 플러그인) |
|--------------------|-----------------------------|
| 서비스 폴더와 코드 하위 폴더 (`apps/`, `src/` …) | `scripts/run.*` (→ runner) |
| 스택 기본 파일 (`package.json`, `vite.config.ts`, `manifest.json`) | `.env.local-dev`, `.env.development`, `.env.production` (→ secrets) |
| `.env.examples` (서비스가 필요로 하는 키 목록, 값 없음) | `build-*`, `deploy-*`, 빌드 단계 스크립트 (→ builder) |
| `proto/` (플랫폼 옵션) | `Dockerfile`, `.dockerignore` (→ builder. 단, 위치는 서비스 폴더 — D15) |
| `views/` (`backend-ssr`) | 루트 `Makefile`, `make.bat` (→ runner) |

#### 플랫폼 목록 (9종)

| id | 성격 | 스킬 (자동) | env 템플릿 | 서비스 기본 폴더 | 이전 이름 |
|----|------|-------------|------------|------------------|-----------|
| `backend` | 일반 단일 백엔드 (API 서버) | `yj-backend` | listen (PORT 8080) | `apps/ services/ domains/ modules/` | (신규) `backend-service` 의 기본 구성 |
| `backend-msa` | gRPC MSA (여러 서비스 + 공유 계약) | `yj-backend-msa` | listen (PORT 8080) | `apps/ services/ domains/ modules/` · 플랫폼에 `proto/` | `backend` |
| `backend-ssr` | 서버 템플릿/SSR 백엔드 | `yj-backend-ssr` | listen (PORT 8080) | `apps/ services/ domains/ modules/ views/` | `backend-service` + SSR 옵션 |
| `frontend` | Vite + React + TS | `yj-frontend` | listen (PORT 5173) | `src/` + `package.json`, `vite.config.ts` | — |
| `mobile-app` | Flutter | `yj-mobile-app` | app | `lib/` | — |
| `pc-app` | Electron | `yj-pc-app` | app | `main/ preload/ renderer/src/` | — |
| `cli` | 단일 CLI | `yj-cli` | app | `apps/ services/ modules/` | — |
| `browser-extension` | MV3 | `yj-browser-extension` + `yj-backend` (`native_*` 용) | app (`native_*` 는 worker) | `src/{background,content,popup,lib}/` + `manifest.json` (`native_*` 는 `apps/ services/ modules/`) | — |
| `scheduler` | 주기 배치 작업 | `yj-scheduler` | worker | `apps/ services/ domains/ modules/` | — |

- `env 템플릿` 은 서비스의 `.env.examples` 와 `secrets` 플러그인이 만드는 환경 파일의 기본 키(PORT 등)를 정한다.
- 현재 `backend-service` 의 env 종류는 worker 다. `backend` / `backend-ssr` 은 HTTP 를 받는 서버이므로 listen 으로 바꾼다 (D11).
- `browser-extension` 의 `native_*` 처럼 서비스 이름에 따라 달라지는 규칙은 `service_variants` 로 표현한다.

```python
# catalog/platforms.py (예시)
Platform(
    id="backend",
    label="backend",
    hint="단일 백엔드 (API)",
    skills=("yj-backend",),
    env_kind="listen",
    env_vars={"__PORT__": "8080"},
    service_dirs=("apps", "services", "domains", "modules"),
    deployable=True,                       # builder 가 Dockerfile 을 만드는 대상
    options=(
        Option("proto", default=False,
               creates=("proto/.gitkeep", "proto/dist/.gitkeep"),
               label="gRPC/protobuf 사용"),
    ),
)
```

#### 플랫폼 옵션

| 플랫폼 | 옵션 | 기본값 | 만드는 것 |
|--------|------|--------|-----------|
| `backend` | proto | off | `backend/proto/`, `backend/proto/dist/` |
| `backend-msa` | proto | **고정** (묻지 않음) | `backend-msa/proto/`, `proto/dist/` |
| `backend-ssr` | proto | off | `backend-ssr/proto/`, `proto/dist/` |
| 나머지 | — | — | — |

- 옵션은 4단계에서 이름을 입력한 직후 묻는다.
- 옵션은 "처음에 무엇을 만들어 줄지"만 정한다. 켜져 있는지는 **디스크에 `proto/` 가 있는지**로 판단하고 매니페스트에 기록하지 않는다. yjcli 는 옵션 폴더를 지우지 않는다.
- `docker` 는 더 이상 플랫폼 옵션이 아니다. `builder` 플러그인이 맡는다 (§4.4).

### 4.3 플러그인 카탈로그

| id | 설명 | 설치 위치 | 필요 | 기본값 (신규) |
|----|------|-----------|------|---------------|
| `runner` | 플랫폼 일괄 실행 + Makefile | `tools/runner/`, 루트 `Makefile`·`make.bat` | `secrets` | on |
| `secrets` | 서비스별 환경 파일 모음 (평문 커밋) | `tools/secrets/` | — | on |
| `builder` | 빌드/배포 스크립트 + 빌드 단계 + Dockerfile | `tools/builder/` | `secrets` | off |

기본값은 `runner` + `secrets` on, `builder` off (D14). 로컬 실행은 대부분 필요하고, 빌드/배포는 구현이 필요한 스텁이라 필요할 때 추가한다.

```python
# catalog/plugins.py (예시)
Plugin(
    id="runner",
    label="플랫폼 일괄 실행 + Makefile",
    requires=("secrets",),
    root_files=(
        Managed("runner/run.sh",  dest="tools/runner/run.sh",  executable=True),
        Managed("runner/run.bat", dest="tools/runner/run.bat"),
        Managed("runner/run.ps1", dest="tools/runner/run.ps1"),
    ),
    makefile=MakeFragment("runner/Makefile.part", "runner/make.bat.part"),
    per_platform=(),
    per_service=(),
    skill_fragment="_shared/plugin-runner.md",
    layout_rows=(
        ("`Makefile`, `make.bat`", "Root entry — `make <platform> [NAME=<service>]`"),
        ("`tools/runner/`", "Platform runner (`run.sh` / `run.bat` / `run.ps1 <platform> [service]`)"),
    ),
)
```

| 필드 | 의미 |
|------|------|
| `requires` | 함께 있어야 하는 플러그인. 위저드·인자 모두에서 자동으로 맞춘다 |
| `root_files` | 저장소에 한 벌만 두는 파일 |
| `per_platform` | 선택한 플랫폼마다 만드는 파일 (예: builder 의 플랫폼별 build/deploy 스크립트) |
| `per_service` | 서비스마다 만드는 파일 (예: secrets 의 환경 파일, builder 의 Dockerfile) |
| `skill_fragment` | 이 플러그인을 고르면 `yj-arch-core` 에 넣을 설명 조각 (§5.3) |
| `layout_rows` | 이 플러그인을 고르면 `AGENTS.md` 저장소 구조 표에 넣을 행 (§4.6) |

플러그인을 새로 추가할 때는 이 항목 하나와 `data/plugins/<id>/` 템플릿만 더한다.

### 4.4 플러그인 상세

#### runner

- **하는 일**: 플랫폼 단위로 서비스를 실행한다. `make backend` 는 `backend/` 아래 서비스를 모두 동시에 띄우고, `make backend NAME=a1` 은 하나만 띄운다 (0.2.x 와 같은 동작).
- **파일**
  - `tools/runner/run.sh`, `run.bat`, `run.ps1` — 저장소에 **한 벌**만 둔다. 첫 인자로 플랫폼을 받는다 (`tools/runner/run.sh backend [a1]`). 0.2.x 에서 플랫폼마다 복사하던 `run.*` 를 하나로 합친 것이다.
  - 루트 `Makefile`, `make.bat` — 매니페스트의 플랫폼 목록으로 타깃을 렌더링한다. 0.2.x 처럼 `*/scripts/run.sh` 를 찾는 방식은 쓰지 않는다.
- **실행 명령**: 서비스별 `RUN_COMMAND` 를 `tools/secrets/<platform>/<service>/.env.local-dev` 에서 읽는다. 그래서 `secrets` 가 필요하다.
- **환경값**: 같은 파일의 나머지 값을 환경변수로 넘겨서 실행한다. 서비스 폴더에 `.env` 를 복사하지 않는다.

#### secrets

- **하는 일**: 서비스별 환경 파일을 `tools/secrets/` 한 곳에 모은다.
- **구조**: `tools/secrets/<platform>/<service>/.env.<environment>` (D16, 코드 폴더 구조와 1:1 대응)
  - 새 서비스마다 `.env.local-dev`, `.env.development`, `.env.production` 을 만든다 (env 템플릿의 기본 키 + `__NAME__`, `__PORT__` 치환).
  - `.env.local-dev` 는 필수 (runner 가 `RUN_COMMAND` 를 읽음). development/production 은 지워도 되고, 다른 `.env.<environment>` 를 추가해도 된다 (0.2.x 규칙 유지).
- **서비스 쪽**: 서비스 폴더에는 `.env.examples` 만 둔다. 이 파일은 플랫폼(코드)이 만들고, 어떤 키가 필요한지 보여주는 문서 역할을 한다.
- **커밋**: `tools/secrets/` 는 **평문으로 커밋한다.** private 저장소를 전제로 하며, 계획 요약과 생성 후 안내에 경고를 표시한다.
- **`.gitignore`**: `tools/secrets/` 를 무시하지 않도록 yjcli 관리 블록에 `!tools/secrets/**` 를 넣는다. 서비스 폴더의 `.env*` 는 `.env.examples` 를 빼고 계속 무시한다 (실수로 서비스 폴더에 만든 `.env` 가 올라가지 않게).
- **파일 정책**: 모두 `seed`. 한 번 만든 뒤에는 사용자 소유이며, yjcli 는 덮어쓰거나 지우지 않는다 (플러그인을 해제해도 남김).

#### builder

- **하는 일**: 빌드/배포 진입점과 빌드 단계, Dockerfile 을 제공한다. 0.2.x 플랫폼 `scripts/` 의 build/deploy 부분과 `plugin-build-*.sh`, 서비스의 `Dockerfile` 을 여기로 옮긴다.
- **파일**

  | 파일 | 정책 | 설명 |
  |------|------|------|
  | `tools/builder/build-common.sh` | managed | 공통 빌드 호스트. `steps/*.sh` 를 모두 실행한 뒤 일반 빌드 가드로 넘어감 |
  | `tools/builder/deploy-common.sh` | managed | 공통 배포 호스트. 해당 빌드를 호출한 뒤 `steps/deploy-*.sh` 실행 |
  | `tools/builder/steps/proto.sh` · `ssr.sh` · `docker.sh` | managed | 0.2.x `plugin-build-*.sh`. 폴더 유무로 스스로 적용 여부를 판단하는 동작은 그대로 (`proto/`, `views/`, `Dockerfile`) |
  | `tools/builder/<platform>/build-{development,production}.sh` | seed | 플랫폼별 빌드 구현 자리. 구현 전까지 안내를 출력하고 실패 |
  | `tools/builder/<platform>/deploy-{development,production}.sh` | seed | 플랫폼별 업로드/롤아웃 구현 자리 |
  | `Dockerfile`, `.dockerignore` (서비스마다) | seed | `deployable=True` 플랫폼(`backend`, `backend-msa`, `backend-ssr`, `frontend`, `scheduler`)의 서비스에만. 위치는 **서비스 폴더** (`backend/a1/Dockerfile`, D15) |
  | `Makefile` 조각 | managed | `make <platform>-build-<env> [NAME=…]`, `make <platform>-deploy-<env> [NAME=…]` |

- **환경값**: 빌드는 `tools/secrets/<platform>/<service>/.env.development` 또는 `.env.production` 을 쓴다. 그래서 `secrets` 가 필요하다.
- **Makefile**: `runner` 없이 `builder` 만 골라도 루트 `Makefile` 은 만든다. `Makefile` 은 선택한 플러그인의 조각을 합쳐 렌더링하므로 builder 타깃만 들어간다. builder 는 runner 를 요구하지 않는다 (D17).
- `build-*`, `deploy-*` 는 0.2.x 처럼 `.sh` 만 제공하고, Windows 의 `make.bat` 은 WSL 로 실행한다.

### 4.5 Makefile 렌더링

```
Makefile = 공통 헤더(help)
         + runner 선택 시:  <platform>, <platform> NAME=…
         + builder 선택 시: <platform>-build-{development,production}, <platform>-deploy-{development,production}
```

구현: `data/plugins/_shared/Makefile`·`make.bat` 템플릿 하나에 `{{#if runner}}` / `{{#if builder}}` 블록을 두고 선택한 플러그인만 남긴다. `make.bat` 은 CRLF 로 쓴다.

- 플랫폼 목록은 매니페스트에서 가져온다. 플랫폼을 추가·제거하면 다시 렌더링한다 (`managed`).
- `make help` 는 실제로 있는 타깃만 보여준다.

### 4.6 AGENTS.md 렌더링

`AGENTS.md` 는 `seed` 파일이다. 처음에 한 번 만들고 그 뒤로는 사용자가 고친다. 다만 선택에 따라 달라지는 부분은 **관리 블록**으로 감싸서 업데이트 때 블록 안만 다시 렌더링한다.

| 관리 블록 | 위치 (AGENTS.md 절) | 내용 | 원천 |
|-----------|---------------------|------|------|
| `<!-- yjcli:skills -->` | Agent operating rules › Skills | 경로 → 스킬 라우팅 표, 스킬 설치 위치 | 설치한 스킬의 `routes`, 선택한 LLM 의 `skills_dir` (§5.4) |
| `<!-- yjcli:layout -->` | Repository layout | 저장소 구조 표 | 공통 행 + 선택한 LLM·플랫폼·플러그인의 행 |

#### 저장소 구조 표 (`yjcli:layout`)

표의 행은 아래 순서로 모은다. 선택하지 않은 LLM·플랫폼·플러그인의 행은 넣지 않는다.

| 순서 | 원천 | 행 예 |
|------|------|-------|
| 1 | 공통 | `AGENTS.md`, `.gitignore`, `.yjcli/manifest.toml` |
| 2 | 선택한 LLM (`catalog/llms.py`) | `CLAUDE.md`, `.claude/skills/`, `.claude/settings.json` · `.cursor/skills/` · `.agents/skills/` |
| 3 | 선택한 플랫폼 (`catalog/platforms.py`) | `backend/` — 성격 + 담당 스킬. 플랫폼 옵션이 있으면 `backend/proto/` (optional) 행 추가 |
| 4 | 선택한 플러그인 (`catalog/plugins.py` 의 `layout_rows`) | runner: `Makefile`·`make.bat`, `tools/runner/` · secrets: `tools/secrets/<platform>/<service>/` · builder: `tools/builder/`, 서비스 `Dockerfile` |

렌더링 예 (`claude` / `backend` + `frontend` / `runner` + `secrets`):

```markdown
## 3. Repository layout

<!-- yjcli:layout -->
| Path | Role |
|------|------|
| `AGENTS.md` | Agent / contributor guide (this file) — source of truth |
| `.gitignore` | Ignore rules (yjcli block is managed) |
| `.yjcli/manifest.toml` | yjcli selection state — do not edit by hand |
| `CLAUDE.md` | Claude Code entry — imports `AGENTS.md` (`@AGENTS.md`); do not edit |
| `.claude/skills/` | Claude Code skills (rendered by yjcli) |
| `.claude/settings.json` | Claude Code settings |
| `backend/` | Single backend services — skill `yj-backend` |
| `backend/proto/` | (optional) gRPC/protobuf contract |
| `frontend/` | Vite + React + TS apps — skill `yj-frontend` |
| `Makefile`, `make.bat` | Root entry — `make <platform> [NAME=<service>]` |
| `tools/runner/` | Platform runner (`run.sh` / `run.bat` / `run.ps1 <platform> [service]`) |
| `tools/secrets/<platform>/<service>/` | Per-service env files (`.env.local-dev`, …) — committed in plain text |
<!-- /yjcli:layout -->

### Project-specific paths

| Path | Role |
|------|------|
| `<path>/` | `<role>` |
```

- 마크다운 표는 행 사이에 주석을 넣으면 깨지므로, 생성되는 표는 **블록 안에 통째로** 두고 사용자가 추가하는 경로는 바로 아래 **별도 표**("Project-specific paths")에 적는다. 이 표는 블록 밖이라 yjcli 가 건드리지 않는다.
- 행의 설명(Role)은 카탈로그에 영어로 적는다. `AGENTS.md` 본문이 영어이기 때문이다.
- `proto/` 처럼 디스크 상태로 켜지는 옵션은 "(optional)" 로 항상 적는다. 옵션은 매니페스트에 없으므로 켜졌는지에 따라 행을 넣고 빼지 않는다.

#### AGENTS.md 템플릿에서 함께 정리할 것

| 대상 | 처리 |
|------|------|
| 저장소 구조 표의 고정 행 (`Makefile`, `<platform>/scripts/*`, `Dockerfile` 설명 등) | 삭제 → `yjcli:layout` 블록으로 대체 |
| `TOOLS.md`, `Diff.md` 행과 관련 절 | 삭제 |
| `CLAUDE.md` 설명 (`refresh with yjcli sync agents`) | 삭제 → LLM 어댑터 행으로 대체 ("imports AGENTS.md") |
| Pointers 표의 "Packaged skills" 행 | 삭제 → 스킬 설치 위치는 `yjcli:skills` 블록에 있음 |
| "Skills are installed under" 목록 | `yjcli:skills` 블록 안으로 이동 |

---

## 5. 스킬 재구성

스킬은 **사용자가 고르지 않는다.** 선택한 플랫폼에서 자동으로 정해지고, 선택한 플러그인에 따라 `yj-arch-core` 의 내용이 달라진다 (§5.4). 이 절은 스킬 구성과 플랫폼·플러그인 연동 방식을 다시 짜는 내용이다.

### 5.1 현재 연동 방식의 문제

| 문제 | 위치 |
|------|------|
| 플랫폼 ↔ 스킬 대응이 세 군데에 따로 적혀 있음 | `AGENTS.md` 라우팅 표, `yj-arch-core` 의 "Fixed platform roots", 각 스킬의 description |
| description 에 다른 플랫폼 이름을 나열함 | 예: `Do not use for backend/, backend-service/, frontend/, …` — 플랫폼을 추가·변경할 때마다 스킬 9개를 모두 고쳐야 함. 일부 스킬만 설치하면 존재하지 않는 플랫폼을 가리키게 됨 |
| 도구 설명이 아키텍처 규칙에 섞여 있음 | `yj-arch-core` 에 `scripts/run.*`, build/deploy, `plugin-build-*.sh`, `.env.*` 규칙이 항상 들어 있음. 해당 도구를 쓰지 않는 저장소에도 적용됨 |
| 같은 내용이 여러 스킬에 중복됨 | gRPC(proto) 옵션 설명이 `yj-backend-msa`·`yj-backend-service` 에, SSR 설명이 두 스킬에 각각 있음 |
| `yj-backend-service` 가 여러 성격을 가짐 | 단일 백엔드 + SSR 옵션 + gRPC 옵션 + `browser-extension/native_*` 담당 |
| 스킬을 그대로 복사함 | 선택한 플랫폼·플러그인·LLM에 맞게 내용을 바꿀 방법이 없음 |

### 5.2 새 스킬 구성

| 스킬 | 종류 | 대상 경로 (`routes`) | 출처 |
|------|------|----------------------|------|
| `yj-arch-core` | core | 모든 경로 | 유지. 플랫폼 목록은 카탈로그에서 렌더링하고, 실행·환경·빌드 규칙은 **선택한 플러그인 조각**으로만 넣음 |
| `yj-backend` | platform | `backend/**`, `browser-extension/native_*/**` | **신규**. `yj-backend-service` 에서 SSR 장을 뺀 것. gRPC 옵션 장은 공유 조각으로 포함 |
| `yj-backend-msa` | platform | `backend-msa/**` | `yj-backend-msa` 유지. 경로를 `backend/` → `backend-msa/` 로 변경. SSR add-on 장 제거 (D6) |
| `yj-backend-ssr` | platform | `backend-ssr/**` | **신규**. `yj-backend-service` 기본 구조 + SSR 장(옵션이 아니라 필수로) + gRPC 옵션 장 |
| `yj-frontend` | platform | `frontend/**` | 유지. 다른 플랫폼 이름 참조만 정리 |
| `yj-mobile-app` | platform | `mobile-app/**` | 유지. 참조 정리 |
| `yj-pc-app` | platform | `pc-app/**` | 유지. 참조 정리 |
| `yj-cli` | platform | `cli/**` | 유지. 참조 정리 |
| `yj-browser-extension` | platform | `browser-extension/**` (`native_*` 제외) | 유지. `native_*` 연결 대상을 `yj-backend` 로 변경 |
| `yj-scheduler` | platform | `scheduler/**` | 유지. 참조 정리 |
| ~~`yj-backend-service`~~ | — | — | **삭제** (`yj-backend` + `yj-backend-ssr` 로 분리) |

플러그인용 스킬은 따로 두지 않는다. 플러그인 규칙은 `yj-arch-core` 안에 조각으로 들어간다.

### 5.3 연동 원칙

**1. 카탈로그를 유일한 기준으로 삼는다.**
플랫폼 → 스킬은 `catalog/platforms.py` 의 `skills`, 스킬 → 경로는 `catalog/skills.py` 의 `routes`, 플러그인 → 설명 조각은 `catalog/plugins.py` 의 `skill_fragment` 에만 적는다. `AGENTS.md` 라우팅 표와 `yj-arch-core` 의 플랫폼 목록·도구 설명은 여기서 렌더링한다.

```python
# catalog/skills.py (예시)
Skill(
    id="yj-backend",
    source="skills/yj-backend",
    kind="platform",                     # core | platform
    routes=("backend/**", "browser-extension/native_*/**"),
    includes=("_shared/backend-base.md", "_shared/grpc-optional.md"),
)
```

**2. 스킬은 "복사"가 아니라 "렌더링"한다.**
패키지 안의 `SKILL.md` 는 템플릿이다. 설치할 때 `core/render.py` 가 아래 자리표시를 채운 뒤 각 LLM 의 `skills_dir` 에 쓴다. 설치된 결과물은 자리표시가 없는 일반 `SKILL.md` 이므로 LLM 쪽에서는 지금과 똑같이 읽는다.

| 자리표시 | 채우는 내용 | 쓰는 곳 |
|----------|-------------|---------|
| `{{platform_roots}}` | **선택한** 플랫폼 루트 목록 + 각 스킬 | `yj-arch-core` |
| `{{skill_routes}}` | 설치한 스킬의 경로 대응 표 | `yj-arch-core`, `AGENTS.md` |
| `{{plugins}}` | **선택한** 플러그인의 `skill_fragment` 를 이어 붙인 것. 하나도 없으면 "실행·빌드 도구 없음, 코드만 다룸" 한 줄 | `yj-arch-core` |
| `{{self_routes}}` | 이 스킬의 대상 경로 | 각 platform 스킬의 description·Scope |
| `{{include:_shared/xxx.md}}` | 공유 조각 본문 | 중복 장 |

**3. description 은 "자기 범위"만 적는다.**
`Do not use for backend/, frontend/, …` 같은 다른 플랫폼 나열을 없애고, `Use only when editing {{self_routes}}.` 만 남긴다. 한 폴더에 한 스킬만 매칭되는 것은 `yj-arch-core` 와 `AGENTS.md` 의 라우팅 표가 보장한다 (D7).

**4. 중복 장과 플러그인 규칙은 공유 조각으로 뺀다.**

| 조각 | 내용 | 들어가는 곳 |
|------|------|-------------|
| `_shared/backend-base.md` | 단일 백엔드 공통 레이어 (`apps/services/domains/modules`) | `yj-backend`, `yj-backend-ssr` |
| `_shared/grpc-optional.md` | 단일 서비스의 gRPC 옵션 (MSA 가 아님, `proto/` 위치, codegen) | `yj-backend`, `yj-backend-ssr` |
| `_shared/plugin-runner.md` | `make <platform>`, `tools/runner/`, `RUN_COMMAND` 위치, 서비스 폴더에 실행 스크립트·Makefile 을 만들지 말 것 | `yj-arch-core` (runner 선택 시) |
| `_shared/plugin-secrets.md` | 환경 파일은 `tools/secrets/<platform>/<service>/` 에만, 서비스에는 `.env.examples` 만, 새 키를 추가하면 `.env.examples` 도 갱신 | `yj-arch-core` (secrets 선택 시) |
| `_shared/plugin-builder.md` | build/deploy 진입점, `steps/` 동작(폴더 유무), Dockerfile 규칙 | `yj-arch-core` (builder 선택 시) |

- `_shared/` 는 설치하지 않는다. 렌더링할 때 본문에 녹여 넣으므로 설치된 스킬은 각자 독립적으로 읽힌다.

**5. 플랫폼 옵션 장은 항상 포함한다.**
옵션(proto)은 디스크 상태가 기준이고 나중에 켤 수 있으므로, 옵션을 선택하지 않았더라도 스킬 본문에서 빼지 않는다. 반면 플러그인 조각은 **선택한 것만** 넣는다 (플러그인은 매니페스트로 관리되고, 추가하면 다시 렌더링되므로).

### 5.4 스킬 자동 결정

```
설치할 스킬     = yj-arch-core ∪ (선택한 각 플랫폼의 skills)
yj-arch-core 내용 = 공통 규칙 + {{platform_roots}} + {{skill_routes}} + {{plugins}}
```

| 선택 예 | 설치되는 스킬 | `yj-arch-core` 에 들어가는 플러그인 조각 |
|---------|---------------|------------------------------------------|
| `backend`, `frontend` / runner, secrets | `yj-arch-core`, `yj-backend`, `yj-frontend` | runner, secrets |
| `backend-msa`, `scheduler` / 전체 | `yj-arch-core`, `yj-backend-msa`, `yj-scheduler` | runner, secrets, builder |
| `browser-extension` / 없음 | `yj-arch-core`, `yj-browser-extension`, `yj-backend` | (없음 — 코드만) |

- 고른 LLM 어댑터의 `skills_dir` 마다 설치한다 (예: Cursor + Claude 면 `.cursor/skills/` 와 `.claude/skills/` 두 곳).
- 위저드에서 묻지 않고, 계획 요약에 `스킬(자동)` 으로만 보여준다.
- 스킬 목록은 플랫폼에서 계산되므로 **매니페스트에 따로 기록하지 않는다.**
- **AGENTS.md 라우팅 표**: "Skills" 절의 `Path | Skill` 표는 설치한 스킬의 `routes` 만으로 렌더링한다. `AGENTS.md` 는 `seed` 파일이므로 이 표만 관리 블록(`<!-- yjcli:skills -->` ~ `<!-- /yjcli:skills -->`)으로 감싸서 업데이트 때 블록 안만 갱신한다 (§4.6).
- **사용자 스킬 보존**: 스킬 디렉터리 안에서 yjcli 가 건드리는 것은 카탈로그에 있는 `yj-*` 스킬 폴더뿐이다. 사용자가 직접 만든 스킬은 읽지도, 지우지도 않는다.
- **스킬 정책**: 렌더링된 스킬 폴더는 `managed` 다. 사용자가 yj 스킬을 고쳤다면(해시 불일치) 다른 managed 파일과 같이 건너뛰고 경고한다 (§6.3).

렌더링된 `AGENTS.md` 라우팅 표 예 (`backend` + `frontend` + `browser-extension` 선택 시):

| Path | Skill |
|------|-------|
| `backend/**` | `yj-backend` |
| `frontend/**` | `yj-frontend` |
| `browser-extension/native_*/**` | `yj-backend` |
| `browser-extension/**` (other) | `yj-browser-extension` |

### 5.5 패키지 내 배치

```
src/yjcli/data/
  skills/
    _shared/
      backend-base.md
      grpc-optional.md
      plugin-runner.md
      plugin-secrets.md
      plugin-builder.md
    yj-arch-core/SKILL.md        # 템플릿 ({{platform_roots}}, {{skill_routes}}, {{plugins}})
    yj-backend/SKILL.md
    yj-backend-msa/SKILL.md
    yj-backend-ssr/SKILL.md
    yj-frontend/SKILL.md
    yj-mobile-app/SKILL.md
    yj-pc-app/SKILL.md
    yj-cli/SKILL.md
    yj-browser-extension/SKILL.md
    yj-scheduler/SKILL.md
```

### 5.6 스킬 검증 (테스트)

- 모든 플랫폼의 `skills` 에 platform 스킬이 하나 이상 있고, 모두 카탈로그에 존재한다.
- 모든 `routes` 의 첫 경로 조각이 카탈로그에 있는 플랫폼 id 다.
- 어떤 두 스킬의 `routes` 도 같은 경로에 겹쳐 매칭되지 않는다 (`browser-extension/native_*` 처럼 더 구체적인 경로가 우선하는 경우는 명시적으로 허용).
- 모든 플러그인의 `skill_fragment` 가 존재한다.
- 플랫폼 스킬 본문에 플러그인 경로(`tools/`, `scripts/`, `.env.local-dev` 등)가 나오지 않는다. 도구 규칙은 플러그인 조각에만 둔다.
- 렌더링 후 남은 `{{…}}` 자리표시가 없다.
- 스킬 템플릿 본문에 카탈로그에 없는 플랫폼 이름(예: `backend-service`)이 나오지 않는다 (린트 테스트).
- `include` 하는 조각이 모두 존재하고, 쓰이지 않는 조각이 없다.

---

## 6. 상태와 업데이트

### 6.1 매니페스트 `.yjcli/manifest.toml`

선택 내용과 설치한 파일을 기록한다. 업데이트와 상태 확인이 이 파일을 기준으로 동작한다. 저장소에 커밋하는 파일이다.

```toml
schema = 1
yjcli_version = "0.3.0"

llms = ["cursor", "claude"]
plugins = ["runner", "secrets"]

[platforms.backend]
services = ["a1", "a2"]

[platforms.frontend]
services = ["f1"]

# 기록하지 않는 것
# - 스킬: 플랫폼에서 계산 (§5.4)
# - 플랫폼 옵션(proto): 디스크 상태가 기준 (§4.2)

# 관리 파일의 설치 당시 해시 (사용자 수정 여부 판단용)
[files]
"Makefile" = { policy = "managed", sha256 = "…" }
"tools/runner/run.sh" = { policy = "managed", sha256 = "…" }
"tools/secrets/backend/a1/.env.local-dev" = { policy = "seed", sha256 = "…" }
".claude/skills/yj-backend/SKILL.md" = { policy = "managed", sha256 = "…" }
```

### 6.2 파일 정책

모든 템플릿 파일은 아래 정책 중 하나를 갖는다. 지금 코드 곳곳에 흩어진 `force` / `skip_existing` / "없을 때만 생성" 같은 규칙을 이 정책 하나로 통일한다.

| 정책 | 의미 | 대상 예 |
|------|------|---------|
| `managed` | yjcli 소유. 업데이트 때 항상 최신으로 교체 | `CLAUDE.md` (`@AGENTS.md`), 렌더링된 yj 스킬 폴더, `Makefile`, `make.bat`, `tools/runner/run.*`, `tools/builder/{build,deploy}-common.sh`, `tools/builder/steps/*` |
| `seed` | 최초 1회만 생성. 그 뒤로는 사용자 소유 | `AGENTS.md`, `settings.json`, 서비스 코드 기본 파일(`package.json` 등), `.env.examples`, `proto/`, `tools/secrets/**`, `tools/builder/<platform>/*`, `Dockerfile`, `.dockerignore` |
| `merge` | 사용자 내용을 보존하면서 yjcli 관리 구간만 갱신 | `.gitignore` (`# >>> yjcli` ~ `# <<< yjcli` 블록), `AGENTS.md` 의 `yjcli:skills`·`yjcli:layout` 블록 |

> `tools/builder/{build,deploy}-common.sh` 는 0.2.x 에서 보존 대상이었지만, 공통 빌드 호스트이므로 `managed` 로 둔다 (D2). 프로젝트별 구현은 `tools/builder/<platform>/*` (seed) 에 한다.

### 6.3 업데이트 동작

업데이트는 "지금 선택"과 "매니페스트에 저장된 선택"의 차이, 그리고 "패키지 버전 차이"를 함께 계산한다.

| 상황 | 동작 |
|------|------|
| 패키지가 새 버전 | `managed` 파일 갱신 (스킬 포함). `seed` 파일은 템플릿이 바뀌었으면 요약에 "템플릿 변경됨(적용 안 함)"으로만 알림 |
| `managed` 파일을 사용자가 수정함 (해시 불일치) | 요약에 `!` 로 표시. 기본은 **건너뜀 + 경고**, `--force` 면 덮어씀 |
| LLM 추가 | 해당 어댑터 파일 생성 + 그 `skills_dir` 에 스킬 렌더링. `AGENTS.md` 의 `yjcli:skills`·`yjcli:layout` 블록 다시 렌더링 |
| LLM 제거 | 해당 어댑터의 `managed` 파일과 그 `skills_dir` 안의 yj 스킬 폴더 삭제. `seed` 와 사용자 스킬은 남기고 안내. `AGENTS.md` 블록 다시 렌더링 |
| 플랫폼 추가 | 플랫폼 코드와 입력한 서비스 생성. 선택된 플러그인의 플랫폼·서비스 파일 생성. 그 플랫폼의 스킬 설치. `yj-arch-core`·`AGENTS.md` 블록·`Makefile` 다시 렌더링 |
| 플랫폼 제거 | **서비스가 있으면 불가** (2단계에서 해제할 수 없음). 비어 있으면 폴더 삭제 여부를 확인. 다른 플랫폼이 쓰지 않는 스킬 삭제, `yj-arch-core`·`AGENTS.md` 블록·`Makefile` 다시 렌더링 |
| 서비스 추가 | 4단계에서 입력한 이름으로 코드 생성 + 선택된 플러그인의 서비스 파일(secrets 환경 파일, Dockerfile) 생성. 이미 있는 이름이면 오류 |
| 서비스 폴더가 사라짐 | 매니페스트에서 정리. `tools/secrets/` 등 플러그인 쪽 파일은 지우지 않고 "고아 파일"로 요약에 안내 |
| 플러그인 추가 | 루트 파일 생성 + **기존 모든 플랫폼·서비스**에 대해 플랫폼·서비스 파일 생성 (이미 있으면 건너뜀). `yj-arch-core`(`{{plugins}}`)·`AGENTS.md` 의 `yjcli:layout` 블록·`Makefile` 다시 렌더링 |
| 플러그인 제거 | 그 플러그인의 `managed` 파일 삭제. `seed` 파일(secrets 값, 구현한 build/deploy 스크립트, Dockerfile)은 **남기고** 안내. 의존하는 플러그인도 함께 제거되며 요약에 표시. `yj-arch-core`·`AGENTS.md` 블록·`Makefile` 다시 렌더링 |
| 패키지에서 스킬이 없어지거나 이름이 바뀜 | 카탈로그의 `replaces` 로 새 스킬에 연결해 교체. 연결이 없으면 요약에 "더 이상 제공되지 않음"으로 표시하고 삭제 여부를 확인 |
| 플랫폼 옵션(proto) 켜기/끄기 | yjcli 가 관여하지 않음. 사용자가 `proto/` 를 만들거나 지우면 builder 의 `steps/proto.sh` 가 알아서 따름 |

삭제는 항상 요약에 펼쳐서 보여주며, `--yes` 를 써도 사용자가 수정한 파일은 삭제하지 않는다.

---

## 7. 내부 아키텍처

### 7.1 핵심 원칙

**질문(Wizard) → 계획(Planner) → 실행(Executor)** 을 분리한다. 파일을 쓰는 곳은 Executor 하나뿐이다.

```
           ┌────────────┐
 CLI args ─┤            │
           │  Selection │◀── Wizard (빈 칸만 질문)
 manifest ─┤            │
           └─────┬──────┘
                 ▼
           ┌────────────┐     ┌──────────┐
           │  Planner   │◀────│ Catalog  │  llms / platforms / plugins / skills
           │            │◀────│ RepoState│  디스크 + manifest 해시
           └─────┬──────┘     └──────────┘
                 ▼
             Plan [FileAction…]   ← plan / --dry-run 은 여기서 출력 후 종료
                 ▼
           ┌────────────┐
           │  Executor  │  create / overwrite / merge / delete / chmod
           └─────┬──────┘
                 ▼
          manifest.toml 저장
```

- `Selection` — 사용자가 고른 값.
  ```python
  Selection(
      llms=["cursor", "claude"],
      platforms={
          "backend":  PlatformPick(services=["a1", "a2"], options={"proto": False}),
          "frontend": PlatformPick(services=["f1"]),
      },
      plugins=["runner", "secrets"],      # requires 를 풀어 둔 결과
      mode="new",
  )
  ```
- `RepoState` — 디스크 현황과 매니페스트를 읽은 결과. 읽기만 한다.
- `Plan` — `FileAction(kind, src, dest, policy, reason, content)` 목록. Planner 는 **코드 계획(플랫폼·서비스)** 과 **플러그인 계획(플러그인마다 root/per_platform/per_service)** 을 따로 만든 뒤 합친다. 스킬 목록 계산과 렌더링(스킬, AGENTS.md 블록, Makefile)도 여기서 끝낸다. 순수 함수로 만들어서 테스트가 쉽도록 한다.
- `Executor` — Plan을 순서대로 적용한다. 실패하면 이미 쓴 파일 목록을 출력하고, 매니페스트는 저장하지 않는다.

### 7.2 패키지 구조

```
src/yjcli/
  cli.py                 # Typer 진입점: 기본 콜백 = 위저드, plan / service add / status / doctor
  catalog/
    __init__.py          # data_root()
    llms.py
    platforms.py         # 플랫폼 + 옵션 + 스킬 대응 + 서비스 변형 (코드만)
    plugins.py           # runner / secrets / builder (+ requires, layout_rows, skill_fragment)
    skills.py            # 스킬 + routes, 스킬 자동 결정, 라우팅 행
  core/
    names.py             # 서비스 이름 목록 파싱/검증 (§2.3)
    selection.py         # Draft: 인자 파싱, 매니페스트 기본값, 누락/검증
    state.py             # RepoState, 감지(new/update), 디스크의 서비스 목록
    manifest.py          # 읽기(tomllib)/쓰기(직접 직렬화)
    planner.py           # Draft + State + Catalog → Plan (코드 계획 + 도구 계획, 렌더링 포함)
    executor.py          # Plan 적용, 빈 폴더 정리, 매니페스트는 마지막에 저장
    render.py            # {{var}} / {{#if}} / {{include:}} 렌더러, 관리 블록 교체
  ui/
    prompts.py           # questionary 체크박스([x])/텍스트/선택 + ← 뒤로, 플러그인 의존성 실시간 토글
    wizard.py            # 단계 진행 (빈 단계만 질문, 확인 후 실행)
    summary.py           # 계획 요약 표 (rich)
  data/
    templates/root/      # AGENTS.md, gitignore, claude-settings.json
    templates/platform/  # envs/<kind>/env.examples, frontend/{package.json, vite.config.ts}
    plugins/_shared/     # Makefile, make.bat (조건 블록)
    plugins/runner/      # run.sh / run.bat / run.ps1
    plugins/secrets/     # <kind>/env.{local-dev,development,production}
    plugins/builder/     # build/deploy-common.sh, steps/, platform/*.sh, service/{Dockerfile,dockerignore}
    skills/              # 스킬 템플릿 + _shared/ (§5.5)
scripts/
  e2e.sh, e2e.py         # 경우의 수별 실제 실행 검증 (§10)
```

패키지 안의 템플릿 파일은 점(.)으로 시작하지 않는 이름(`env.examples`, `gitignore`, `dockerignore`)으로 두고 설치할 때 이름을 바꾼다. 점 파일은 yjcli 저장소 자체의 `.gitignore` 규칙과 빌드(wheel) 제외 규칙에 걸리기 때문이다.

현재 코드는 참고만 하고 새 구조로 다시 작성한다. 옮겨 올 내용:

| 현재 | 새 위치 |
|------|---------|
| `modules/constants.py` | `catalog/platforms.py` |
| `data/templates/platform/scripts/run.*` | `data/plugins/runner/` (플랫폼별 복사 → 한 벌) |
| `data/templates/Makefile`, `make.bat` | `data/plugins/_shared/Makefile`, `make.bat` (조건 블록) |
| `data/templates/platform/envs/<kind>/.env.{local-dev,development,production}` | `data/plugins/secrets/<kind>/` |
| `data/templates/platform/envs/<kind>/.env.examples` | `data/templates/platform/envs/<kind>/` (코드 쪽에 남음) |
| `data/templates/platform/scripts/{build,deploy}-*.sh` | `data/plugins/builder/` |
| `data/templates/platform/scripts/plugin-build-*.sh` | `data/plugins/builder/steps/` |
| `data/templates/platform/service/Dockerfile`, `.dockerignore`, `_SERVICE_BOILERPLATE_PLUGINS` | `data/plugins/builder/` + `catalog/platforms.py` 의 `deployable` |
| `data/templates/Diff.md`, `data/templates/TOOLS.md` | 삭제 |
| `data/templates/AGENTS.md` 의 스킬 표 (하드코딩) | `catalog/skills.py` 의 `routes` 로 렌더링 |
| `services/scaffold.py` | `catalog/*` (데이터) + `core/planner.py` (로직) |
| `services/sync.py`, `services/wiring.py` | `core/planner.py` (정책 기반 액션 생성) |
| `modules/fsutil.py` | `core/executor.py` |
| `modules/prompt.py` | `ui/prompts.py` |

### 7.3 의존성

| 용도 | 후보 | 제안 |
|------|------|------|
| 체크박스·텍스트 입력 | `questionary`, `InquirerPy` | **questionary** (prompt_toolkit 기반). `checkbox` 의 선택 표시를 `[x]` / `[ ]` 로 지정할 수 있고, `text` 에 검증 함수를 붙여 잘못된 이름이면 같은 화면에서 다시 받을 수 있음. 플러그인 의존성 자동 체크는 선택 변경 콜백으로 구현 |
| 요약 표·색상 | `rich` | **rich** (Typer 가 이미 선택적으로 사용) |
| 매니페스트 | `tomllib` (읽기, 표준) + `tomli-w` (쓰기) | 둘 다 |
| 스킬·Makefile·AGENTS.md 렌더링 | 직접 구현 (`{{…}}` 치환) / `jinja2` | **직접 구현** (D12). 자리표시 몇 종과 조각 합치기면 충분하고 의존성을 늘리지 않음 |

TTY 가 아니면 프롬프트 라이브러리를 아예 쓰지 않고 §3.2 의 누락 인자 오류로 처리한다.

---

## 8. 단계 정의 (ui/steps.py)

| # | 단계 | 입력 | 건너뛰는 조건 | 영향을 주는 뒤 단계 |
|---|------|------|---------------|---------------------|
| 0 | 상태 | 자동 감지 | 항상 자동 (`--mode` 로 덮어쓰기) | 전체 기본값 |
| 1 | LLM | 체크박스 `[x]`, 최소 1개 | `--llm` | 5 |
| 2 | 플랫폼 | 체크박스 `[x]`, 최소 1개 | `--platform` 또는 `--name` 으로 플랫폼이 정해짐 | 4, 5 |
| 3 | 플러그인 | 체크박스 `[x]`, 0개 이상, `requires` 자동 맞춤 | `--plugin` | 5 |
| 4 | 서비스 이름 + 플랫폼 옵션 | 선택한 플랫폼마다 한 화면: 이름 목록(공백/`,`) → 옵션 체크박스 (있는 플랫폼만) | 해당 플랫폼의 `--name` (옵션은 `--option` 또는 기본값) | 5 |
| 5 | 확인 | Y / n / back / d | `--yes` 또는 `--dry-run` | — |

- 4단계는 플랫폼 수만큼 하위 화면을 가진다. `--name` 으로 일부 플랫폼만 채웠다면 나머지 플랫폼만 묻는다.
- 단계마다 `validate(selection) -> list[str]` 를 두어서 인자로 받은 값도 위저드 입력과 같은 규칙으로 검증한다 (예: 플랫폼에 없는 옵션 지정 금지, 이름 규칙 §2.3, 알 수 없는 플러그인).
- 업데이트 모드의 기본 선택은 매니페스트 값이다. 신규 모드의 기본값은 카탈로그의 `default` 다.

---

## 9. 단계별 구현 계획

| 단계 | 내용 | 완료 기준 |
|------|------|-----------|
| M1. 카탈로그 + 코어 | `catalog/` (9개 플랫폼, 옵션, 스킬 대응, LLM), `core/selection·planner·executor·render`. 코드 계획만 | Planner 단위 테스트 통과, `plan` 이 코드만 있는 신규 설치 계획을 출력 |
| M2. 플러그인 | `catalog/plugins.py`, `data/plugins/{runner,secrets,builder}`, 스크립트 경로를 `tools/` 기준으로 수정, Makefile 조각 렌더링, AGENTS.md `yjcli:layout` 블록, 의존성 풀기 | 각 플러그인 단독·조합 설치 테스트 통과, `make backend NAME=a1` 이 `tools/secrets` 의 `RUN_COMMAND` 로 실행됨 |
| M3. 스킬 재구성 | `yj-backend-service` 분리 → `yj-backend` / `yj-backend-ssr`, `yj-backend-msa` 경로 변경, `yj-arch-core` 에서 도구 규칙을 플러그인 조각으로 분리, `_shared/` 추출, description 정리, 자리표시 도입 | §5.6 검증 테스트 통과 |
| M4. 매니페스트 | `manifest.toml` 읽기/쓰기, 파일 정책, 해시 기록 | 신규 설치 후 매니페스트 생성, `status` 동작 |
| M5. 위저드 | `yjcli` 기본 진입, 플랫폼·플러그인 체크박스, 플랫폼별 이름 입력, 인자로 단계 건너뛰기, 요약/확인 | 대화형·비대화형 모두 E2E 테스트 통과. `backend: a1,a2` + `frontend: f1` 입력 시 `backend/a1`, `backend/a2`, `frontend/f1` 생성 |
| M6. 업데이트 | diff 계산, 플랫폼·서비스·LLM·플러그인 추가/제거, 사용자 수정 감지, `--force` | §6.3 표의 각 행에 대한 테스트 |
| M7. 문서/릴리스 | README 재작성, 기존 명령 코드 삭제, 0.3.0 배포 | — |

M3(스킬)는 M1·M2 와 병행할 수 있다. 렌더러(`core/render.py`)만 먼저 있으면 된다.

---

## 10. 테스트 전략

- **Planner 단위 테스트**: `Selection` + 가짜 `RepoState` → 예상 `Plan`. 파일을 쓰지 않으므로 빠르고, 대부분의 규칙(정책, 업데이트 diff, 스킬 자동 결정, 플러그인 의존성, 플러그인별 생성 파일)을 여기서 검증한다.
- **코드/도구 분리 테스트**: 플러그인 없이 설치하면 플랫폼·서비스 폴더에 `scripts/`, `.env.local-dev` 등 도구 파일이 하나도 없고 `tools/` 도 생기지 않는다.
- **이름 파싱 테스트**: `a1,a2` · `a1 a2` · `a1, a2` · `a1,,a2` · 중복 · 예약어 · 잘못된 문자 (§2.3).
- **플러그인 테스트**: 의존성 자동 추가/해제, 플러그인 추가 시 기존 서비스 전체에 파일 생성, 플러그인 제거 시 seed 보존, runner 실행(`RUN_COMMAND` 읽기, 환경값 전달), `.gitignore` 가 `tools/secrets/` 를 무시하지 않음.
- **AGENTS.md 블록 테스트**: `yjcli:layout`·`yjcli:skills` 블록에 선택한 LLM·플랫폼·플러그인의 행만 있고, 블록 밖(사용자 표 등)은 업데이트 후에도 그대로다. 플러그인을 추가/제거하면 해당 행만 바뀐다.
- **스킬 검증 테스트**: §5.6 항목.
- **Executor 테스트**: 임시 디렉터리에 Plan을 적용한 뒤 결과 트리와 권한(`chmod +x`)을 확인한다.
- **E2E (`scripts/e2e.sh`)**: 저장소 안 `sandbox/<case>/` (git 제외)에 실제로 `yjcli` 를 실행하고 결과 트리·내용·`make` 실행·git 무시 규칙까지 확인한다. 케이스는 실행 후 남겨 두어 직접 열어 볼 수 있다. 대화형 위저드도 키 입력(space, ←, 텍스트)을 주입해 끝까지 진행한다.

  | 케이스 | 확인 내용 |
  |--------|-----------|
  | 01-code-only | 플러그인 없음 → `tools/`·Makefile·Dockerfile 없음, CLAUDE.md = `@AGENTS.md` |
  | 02-runner-secrets | runner → secrets 자동 추가, `make backend [NAME=a1]` 실제 실행, `tools/secrets` 는 git 추적·서비스 `.env*` 는 무시 |
  | 03-builder | 배포 가능한 플랫폼에만 Dockerfile, 플랫폼별 스텁 실행 권한, 빌드 스텝 출력 |
  | 04-builder-without-runner | Makefile 에 빌드 타깃만 |
  | 05-backend-variants | backend-msa proto 고정, backend proto 옵션, backend-ssr views, 스킬 분리 |
  | 06-browser-extension | `native_*` 변형 구조, 라우팅 순서 |
  | 07-everything | 전체 조합: 미렌더링 `{{`·옛 이름(`backend-service`, `plugin-build`, Diff/TOOLS) 없음 |
  | 08-idempotent | 같은 선택으로 재실행 → 변경 0 |
  | 09-service-add | 새 서비스만 생성, 사용자 파일·옵트아웃(Dockerfile 삭제) 보존 |
  | 10-plugin-add-remove | 추가 시 기존 서비스 전체에 생성, 제거 시 managed 만 삭제 |
  | 11-modified-managed | 사용자가 고친 managed 파일은 건너뜀, `--force` 로 덮어씀 |
  | 12-llm-remove | yj 스킬만 삭제, 사용자 스킬 보존 |
  | 13-platform-remove-guard | 서비스가 있는 플랫폼 해제 거부, `-n` 만으로 플랫폼 추가 |
  | 14-validation | 모든 오류를 한 번에, 파일을 만들지 않음 |
  | 15-dry-run | `--dry-run`·`plan` 은 파일을 만들지 않음 |
  | 16-agents-md-user-edits | 블록 밖 사용자 편집 보존 |
  | 17-wizard | 대화형 전체 흐름 (←, 최소 선택, 의존성 자동 체크, 빈 이름 재입력) |
  | 18-status-doctor | `status`·`doctor` |
- **단위 테스트 (`tests/test_core.py`)**: 렌더러, 이름 파싱, 플러그인 의존성, 스킬 카탈로그 검증(§5.6), Planner(코드만 / seed 는 새 주인일 때만), 매니페스트 왕복.

---

## 11. 결정 사항

제안대로 확정했다 (2026-11-03). 본문은 이 결정을 반영해 작성되어 있다.

| # | 질문 | 결정 | 관련 |
|---|------|------|------|
| D1 | `CLAUDE.md` 를 복사본(mirror)으로 둘지, `@AGENTS.md` import 로 바꿀지 | **import**. 실행할 때마다 다시 맞출 필요가 없고, `CLAUDE.md` 가 원본과 어긋날 일이 없음 | §4.1 |
| D2 | `tools/builder/{build,deploy}-common.sh` 를 managed 로 둘지 | managed. 공통 빌드 호스트이므로 사용자가 고칠 파일이 아님. 플랫폼별 스크립트(`tools/builder/<platform>/*`)만 seed | §4.4, §6.2 |
| D3 | 매니페스트 위치/형식 | `.yjcli/manifest.toml` (커밋 대상). 디렉터리로 둬서 나중에 캐시 등을 추가할 여지를 남김 | §6.1 |
| D4 | `.gitignore` 를 merge 정책으로 바꿀지 | 바꾼다. 지금은 덮어쓰기라 사용자 항목이 사라짐. `tools/secrets/` 예외 규칙도 관리 블록에 넣어야 함 | §4.4, §6.2 |
| D5 | 추가 LLM(Gemini, Copilot 등)을 첫 릴리스에 넣을지 | 어댑터 구조만 준비하고 첫 릴리스는 3종 유지 | §4.1 |
| D6 | `yj-backend-msa` 의 SSR add-on 장을 없앨지 | 없앤다. SSR 은 `backend-ssr` 플랫폼으로 일원화. MSA 안에서 HTML 을 렌더링해야 하면 그 서비스는 `backend-ssr` 로 분리 | §5.2 |
| D7 | 스킬 description 에서 다른 플랫폼 나열을 없앨지 | 없앤다. 자기 범위만 적고 라우팅은 `yj-arch-core`·`AGENTS.md` 가 보장 | §5.3 |
| D8 | `builder` 가 `deployable` 플랫폼의 모든 서비스에 Dockerfile 을 만들지, 따로 물을지 | 모두 만든다. 필요 없으면 서비스별로 지우면 됨 (`steps/docker.sh` 가 Dockerfile 유무로 판단) | §4.4 |
| D9 | `yjcli service add` 단독 명령을 유지할지 | 유지. 업데이트 모드에서 4단계만 실행하는 단축 명령 (`yjcli service add -n backend=a3`) | §3.1 |
| D10 | 업데이트 모드에서 서비스가 있는 플랫폼의 해제를 막을지 | 막는다. 서비스 삭제는 사용자가 폴더를 지우는 것으로만 하고, yjcli 는 서비스를 지우지 않음 | §2.6, §6.3 |
| D11 | `backend` / `backend-ssr` 의 env 템플릿을 worker 에서 listen 으로 바꿀지 | 바꾼다. 둘 다 HTTP 를 받는 서버이므로 PORT 가 있어야 함 | §4.2 |
| D12 | 스킬·Makefile 렌더링을 직접 구현할지, `jinja2` 를 쓸지 | 직접 구현. 자리표시 몇 종과 조각 합치기면 충분하고 의존성을 늘리지 않음 | §5.3, §4.5 |
| D13 | `backend-msa` 에서 `proto` 를 고정(해제 불가)으로 둘지 | 고정. MSA 의 서비스 간 계약이 gRPC 이므로 필수 | §4.2 |
| D14 | 신규 설치 때 플러그인 기본 선택 | `runner` + `secrets` on, `builder` off. 로컬 실행은 대부분 필요하고, 빌드/배포는 구현이 필요한 스텁이라 필요할 때 추가 | §4.3 |
| D15 | `Dockerfile` 위치: 서비스 폴더 vs `tools/builder/docker/<platform>/<service>/` | **서비스 폴더**. Docker 빌드 컨텍스트가 서비스 폴더라 관례상 같은 곳에 두는 편이 자연스럽고, 도구에서 쓰기도 쉬움. 대신 "서비스 폴더는 코드만" 원칙의 예외가 됨 | §2.5, §4.4 |
| D16 | secrets 폴더 구조: `tools/secrets/<platform>/<service>/.env.<env>` vs 평평한 `tools/secrets/<platform>.<service>.env.<env>` | 중첩 구조. 코드 폴더 구조와 1:1 로 대응해 찾기 쉬움 | §4.4 |
| D17 | `builder` 만 고르고 `runner` 는 고르지 않은 경우 `Makefile` 을 만들지 | 만든다. `Makefile` 은 선택한 플러그인 조각을 합쳐 렌더링하므로 builder 타깃만 들어감. builder 가 runner 를 요구하지 않음 | §4.4, §4.5 |
| D18 | 빌드 단계 스크립트 이름 | `plugin-build-*.sh` → `steps/*.sh` 로 변경. 새 "플러그인" 개념과 이름이 겹치지 않게 함 | §4.4 |

---

## 12. 구현 메모 (기획과 달라진 세부 사항)

| 항목 | 기획 | 구현 |
|------|------|------|
| Makefile 렌더링 | 플러그인별 조각을 합침 | 템플릿 하나 + `{{#if runner}}`/`{{#if builder}}` 블록 (결과는 같음) |
| `.gitignore` 관리 블록 표시 | `# >>> yjcli` ~ `# <<< yjcli` | `# >>> yjcli:managed` ~ `# <<< yjcli:managed` |
| `catalog/files.py`, `ui/steps.py`, `commands/` | 별도 모듈 | 루트 파일은 `planner.py`, 단계 진행은 `ui/wizard.py`, 명령은 `cli.py` 에 둠 |
| 매니페스트 쓰기 | `tomli-w` | 직접 직렬화 (구조가 단순해 의존성을 늘리지 않음) |
| 매니페스트 `files` | 모든 템플릿 파일 | 도구 파일(managed/seed/merge)만 기록. 서비스 코드 파일은 사용자 소유라 기록하지 않음 |
| seed 생성 시점 | "최초 1회" | 주인(LLM·플랫폼·서비스·플러그인)이 이번 실행에서 새로 생길 때만 생성. 사용자가 지운 seed(예: Dockerfile 옵트아웃)를 업데이트 때 되살리지 않기 위함 |
| 비대화형 실행 | 누락 인자만 오류 | 확인 단계가 없으므로 `--yes` 또는 `--dry-run` 도 요구 |
| `--name` 만 준 업데이트 | — | 기존 플랫폼에 더해짐. `--platform` 을 주면 그 목록이 전체 선택이 됨 |
| 빌드 스텁 | `build-common.sh` 가 가드로 실패 | 공통 호스트(managed)는 스텝만 실행하고, 플랫폼별 `build-<env>.sh`(seed)가 구현 안내 후 실패 |
