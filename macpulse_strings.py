"""Localised strings for macpulse (Azerbaijani, English, Russian).

Kept in its own module so the scanner stays readable: adding a language means
adding one dict here and nothing else. Every value is a str.format template —
placeholders are named, never positional, so translators can reorder freely.
"""

LANGS = ("az", "en", "ru")
FALLBACK = "en"

STRINGS = {
    # ------------------------------------------------------------------ English
    "en": {
        "app.tagline": "Mac health for the AI-development era",
        "nav.overview": "Overview",
        "nav.memory": "Memory",
        "nav.processes": "Processes",
        "nav.ai": "AI tools",
        "nav.browser": "Browser & locks",
        "nav.containers": "Containers",
        "btn.rescan": "Rescan",
        "btn.fixall": "Fix all safe",
        "btn.fixall.n": "Fix all safe ({n})",
        "btn.quit": "Quit",
        "menu.open": "Open panel…",
        "btn.fix": "Fix",
        "btn.working": "Working…",
        "ui.vitals": "Vitals",
        "ui.free": "Memory free",
        "ui.swap": "Swap",
        "ui.disk": "Disk free",
        "ui.uptime": "Uptime",
        "ui.days": "days",
        "ui.recoverable": "Recoverable",
        "ui.findings": "Findings",
        "ui.nofindings": "Nothing worth reporting",
        "ui.allgood": "This Mac is in good shape right now.",
        "ui.nothing.section": "Nothing to report in this section.",
        "ui.nofix": "No automatic fix",
        "ui.corehours": "{n} core-hours",
        "ui.scanning": "Scanning…",
        "ui.stopped": "macpulse stopped.",
        "ui.closetab": "You can close this tab.",
        "ui.applied": "{done} of {total} fixes applied.",
        "ui.failed": "Could not apply: {err}",
        "ui.scanfail": "Scan failed: {err}",
        "ui.readonly": "Read-only until you press Fix",
        "ui.confirm": "Apply these fixes? Processes will be stopped.",
        "grade.healthy": "Healthy",
        "grade.attention": "Needs attention",
        "grade.struggling": "Struggling",
        "fix.stop.one": "Stop PID {pid}",
        "fix.stop.many": "Stop {n} processes",
        "fix.clearlock": "Clear {app} lock",
        "fix.quitdocker": "Quit Docker Desktop",
        "res.stopped": "Stopped {done} of {total} processes",
        "res.cleared": "Cleared {n} stale lock files for {app}",
        "res.dockerquit": "Docker Desktop has quit",
        "res.dockerstuck": "Docker Desktop did not quit — it may be asking to save something",

        "cpu.t": "{name} has burned {hours} core-hours",
        "cpu.d": "Running {days} days at {pct}% of a core sustained. Its resident size "
                 "is only {size}, which is why size-based cleaners never report it — "
                 "the cost is heat, battery and swap thrash, not disk.",
        "ghost.t": "{name} is still running from {where}",
        "ghost.t.many": "{name} is still running from {where} ({n} processes)",
        "ghost.where.volume": "a volume that is no longer mounted",
        "ghost.where.app": "a deleted application",
        "ghost.d": "Nothing exists at {path} any more, yet it has been alive {days} days "
                   "holding {size}. The app's uninstaller went with the app, so no disk "
                   "cleanup will ever reach this.",
        "ai.t": "{n} {host} sessions are open, costing {size}",
        "ai.d": "Each session starts its own complete MCP server stack instead of sharing "
                "one, so the cost multiplies by the number of open tabs — about {each} "
                "each. It never appears in Activity Monitor as one line, because it is "
                "spread across dozens of small node processes.",
        "mcpdead.t": "MCP server '{name}' is configured but {verdict}",
        "mcpdead.d": "It is loaded into every AI session, asked to start, and fails every "
                     "time — currently across {n} session(s). Either authorise it or take "
                     "it out of the global config.",
        "mcp.unauth": "returns HTTP {code} — not authorised",
        "mcp.unreachable": "is unreachable",
        "mcpcost.t": "MCP server '{name}' is using {size} across {n} processes",
        "mcpcost.d": "stdio MCP servers start once per session. If you keep many AI tabs "
                     "open, multiply this by the tab count.",
        "headless.t": "{n} headless browser(s) left over from automation",
        "headless.d": "Started by a script that never shut them down — the oldest has run "
                      "{days} days. They hold {size}, keep a debugging port open, and can "
                      "lock a browser profile so the real browser refuses to start.",
        "lock.t": "{app} is held by a stale lock (dead PID {pid})",
        "lock.d": "The lock points at a process that no longer exists, left behind when "
                  "the app was force-quit. Until it is removed the app may refuse to "
                  "launch, usually failing silently or with error -1712.",
        "docker.t": "Docker Desktop is running with no containers ({size})",
        "docker.d": "Docker keeps a Linux virtual machine alive whether or not anything "
                    "runs in it. At zero containers that memory buys you nothing.",
        "sim.t": "{n} iOS Simulator process(es) using {size}",
        "sim.d": "Simulators keep running after Xcode is closed.",
        "swap.t": "{used} GB of memory has spilled onto disk (this Mac has {ram} GB of RAM)",
        "swap.d": "Swap this large means the apps you run need more memory than the Mac has, so every switch waits on the disk. It does not shrink on its own: quit the biggest app listed here, or restart — the Mac has been up {days} days.",
        "pressure.t": "Only {pct}% of memory is free",
        "pressure.d": "Below about a quarter free, macOS compresses and swaps aggressively "
                      "and everything feels slow — this is the state that ends in the "
                      "'your system has run out of application memory' dialog.",
        "disk.t": "Only {free} GB free on disk",
        "disk.d": "When RAM runs short macOS moves memory to disk ({swap} GB right now). With the disk this full there is nowhere left to put it, and macOS starts force-quitting apps — the 'run out of application memory' dialog. Free space first; the biggest regenerable items are listed.",
        "hog.t": "{name} is using {size} — {pct}% of this Mac's {ram} GB",
        "hog.d": "One app holding this much memory pushes everything else into swap. If it did not need this much when it started, quitting and reopening it gives the memory back.",
        "hog.browser.d": "It is almost always one or two tabs, not the browser itself. Open the browser's Task Manager (Shift+Esc in Chrome), sort by memory and close the top tab. Quitting and reopening also works — tabs come back, the memory is returned.",
        "uptime.t": "Up {days} days with swap under pressure",
        "uptime.d": "Long uptime is not a fault by itself, but combined with saturated "
                    "swap a restart is the cheapest full reset available.",
        "swarm.t": "{n} copies of {name} using {size}",
        "swarm.d": "Helper processes are normal for browsers and editors. Listed so you "
                   "can see where the memory actually went, not because it is wrong.",
    },

    # --------------------------------------------------------------- Azerbaijani
    "az": {
        "app.tagline": "AI dövrü üçün Mac sağlamlığı",
        "nav.overview": "Ümumi",
        "nav.memory": "Yaddaş",
        "nav.processes": "Proseslər",
        "nav.ai": "AI alətlər",
        "nav.browser": "Brauzer və kilidlər",
        "nav.containers": "Konteynerlər",
        "btn.rescan": "Yenilə",
        "btn.fixall": "Hamısını düzəlt",
        "btn.fixall.n": "Hamısını düzəlt ({n})",
        "btn.quit": "Bağla",
        "menu.open": "Paneli aç…",
        "btn.fix": "Düzəlt",
        "btn.working": "İcra olunur…",
        "ui.vitals": "Göstəricilər",
        "ui.free": "Boş yaddaş",
        "ui.swap": "Swap",
        "ui.disk": "Diskdə boş",
        "ui.uptime": "İşləmə müddəti",
        "ui.days": "gün",
        "ui.recoverable": "Geri alına bilər",
        "ui.findings": "Tapıntılar",
        "ui.nofindings": "Bildiriləsi bir şey yoxdur",
        "ui.allgood": "Bu Mac hazırda yaxşı vəziyyətdədir.",
        "ui.nothing.section": "Bu bölmədə tapıntı yoxdur.",
        "ui.nofix": "Avtomatik düzəliş yoxdur",
        "ui.corehours": "{n} nüvə-saat",
        "ui.scanning": "Skan edilir…",
        "ui.stopped": "macpulse dayandırıldı.",
        "ui.closetab": "Bu tab-ı bağlaya bilərsən.",
        "ui.applied": "{total} düzəlişdən {done} tətbiq olundu.",
        "ui.failed": "Tətbiq olunmadı: {err}",
        "ui.scanfail": "Skan alınmadı: {err}",
        "ui.readonly": "Düzəlt düyməsinə basana qədər heç nəyə toxunulmur",
        "ui.confirm": "Bu düzəlişlər tətbiq olunsun? Proseslər dayandırılacaq.",
        "grade.healthy": "Sağlam",
        "grade.attention": "Diqqət tələb edir",
        "grade.struggling": "Çətinlik çəkir",
        "fix.stop.one": "PID {pid} dayandır",
        "fix.stop.many": "{n} prosesi dayandır",
        "fix.clearlock": "{app} kilidini təmizlə",
        "fix.quitdocker": "Docker Desktop-u bağla",
        "res.stopped": "{total} prosesdən {done} dayandırıldı",
        "res.cleared": "{app} üçün {n} köhnə kilid faylı silindi",
        "res.dockerquit": "Docker Desktop bağlandı",
        "res.dockerstuck": "Docker Desktop bağlanmadı — nə isə soruşurusa, özü cavab gözləyir",

        "cpu.t": "{name} {hours} nüvə-saat yandırıb",
        "cpu.d": "{days} gündür bir nüvənin {pct}%-ni davamlı tutur. Tutduğu yaddaş cəmi "
                 "{size}-dır — ölçüyə baxan təmizləyicilər məhz buna görə onu heç vaxt "
                 "görmür. Xərc diskdə yox, istilikdə, batareyada və swap yükündədir.",
        "ghost.t": "{name} hələ də {where} işləyir",
        "ghost.t.many": "{name} hələ də {where} işləyir ({n} proses)",
        "ghost.where.volume": "artıq qoşulmamış diskdən",
        "ghost.where.app": "silinmiş proqramdan",
        "ghost.d": "{path} ünvanında artıq heç nə yoxdur, amma proses {days} gündür yaşayır "
                   "və {size} tutur. Proqramın öz silici aləti proqramla birlikdə getdiyi "
                   "üçün heç bir disk təmizliyi buna çata bilməz.",
        "ai.t": "{n} {host} sessiyası açıqdır, {size} tutur",
        "ai.d": "Hər sessiya MCP serverlərini paylaşmaq əvəzinə öz tam dəstini qaldırır, "
                "ona görə xərc açıq tab sayına vurulur — hərəsi təxminən {each}. Bu, "
                "Activity Monitor-da tək sətir kimi görünmür, çünki onlarla kiçik node "
                "prosesinə yayılıb.",
        "mcpdead.t": "'{name}' MCP serveri konfiqdədir, amma {verdict}",
        "mcpdead.d": "Hər AI sessiyasına yüklənir, başlamağa çağırılır və hər dəfə uğursuz "
                     "olur — hazırda {n} sessiyada. Ya icazəni ver, ya da qlobal konfiqdən "
                     "çıxar.",
        "mcp.unauth": "HTTP {code} qaytarır — icazə yoxdur",
        "mcp.unreachable": "əlçatmazdır",
        "mcpcost.t": "'{name}' MCP serveri {n} prosesdə {size} tutur",
        "mcpcost.d": "stdio MCP serverləri hər sessiyada bir dəfə başlayır. Çox AI tab-ı "
                     "saxlayırsansa, bunu tab sayına vur.",
        "headless.t": "Avtomatlaşdırmadan {n} headless brauzer qalıb",
        "headless.d": "Onları başladan skript heç vaxt bağlamayıb — ən köhnəsi {days} "
                      "gündür işləyir. {size} tutur, debug portunu açıq saxlayır və "
                      "brauzer profilini kilidləyib əsl brauzerin açılmasına mane ola bilər.",
        "lock.t": "{app} köhnə kilidlə bloklanıb (ölü PID {pid})",
        "lock.d": "Kilid artıq mövcud olmayan prosesə işarə edir — proqram sərt bağlananda "
                  "qalıb. Silinməyincə proqram açılmaya bilər, adətən səssizcə və ya "
                  "-1712 xətası ilə.",
        "docker.t": "Docker Desktop konteyner olmadan işləyir ({size})",
        "docker.d": "Docker içində nə isə işləyib-işləməməsindən asılı olmayaraq bir Linux "
                    "virtual maşınını canlı saxlayır. Sıfır konteynerdə bu yaddaş sənə "
                    "heç nə qazandırmır.",
        "sim.t": "{n} iOS Simulator prosesi {size} tutur",
        "sim.d": "Simulyatorlar Xcode bağlandıqdan sonra da işləməyə davam edir.",
        "swap.t": "Yaddaşın {used} GB-ı diskə daşıb (bu Mac-də {ram} GB RAM var)",
        "swap.d": "Bu qədər swap o deməkdir ki, açıq proqramlara Mac-in RAM-ından çox yaddaş lazımdır və hər keçid diski gözləyir. Swap öz-özünə azalmır: burada göstərilən ən böyük proqramı bağla, ya da Mac-i yenidən başlat — {days} gündür söndürülməyib.",
        "pressure.t": "Yaddaşın yalnız {pct}%-i boşdur",
        "pressure.d": "Dörddə birdən az boş qalanda macOS aqressiv şəkildə sıxır və swap "
                      "edir, hər şey yavaşlayır — «sistemdə tətbiq yaddaşı qalmadı» "
                      "dialoqu ilə bitən vəziyyət elə budur.",
        "disk.t": "Diskdə cəmi {free} GB boş yer qalıb",
        "disk.d": "RAM çatmayanda macOS yaddaşı diskə köçürür (hazırda {swap} GB). Disk bu qədər dolu olanda köçürməyə yer qalmır və macOS proqramları məcburi bağlamağa başlayır — «tətbiq yaddaşı qalmadı» pəncərəsi budur. Əvvəl yer aç; yenidən yarana bilən ən böyük şeylər aşağıdadır.",
        "hog.t": "{name} {size} tutur — bu Mac-in {ram} GB-ının {pct}%-i",
        "hog.d": "Bir proqramın bu qədər yaddaş tutması qalan hər şeyi swap-a itələyir. Açılanda bu qədər lazım deyildisə, bağlayıb yenidən açmaq yaddaşı geri qaytarır.",
        "hog.browser.d": "Demək olar ki, həmişə günahkar brauzer yox, bir-iki tabdır. Brauzerin Task Manager-ini aç (Chrome-da Shift+Esc), yaddaşa görə sırala və ən yuxarıdakı tabı bağla. Bağlayıb yenidən açmaq da olar — tablar geri gəlir, yaddaş boşalır.",
        "uptime.t": "{days} gündür işləyir və swap təzyiq altındadır",
        "uptime.d": "Uzun işləmə müddəti özlüyündə problem deyil, amma dolu swap ilə "
                    "birlikdə yenidən başlatmaq ən ucuz tam sıfırlamadır.",
        "swarm.t": "{name} proqramının {n} nüsxəsi {size} tutur",
        "swarm.d": "Köməkçi proseslər brauzer və redaktorlar üçün normaldır. Səhv olduğu "
                   "üçün yox, yaddaşın hara getdiyini görəsən deyə sadalanıb.",
    },

    # ------------------------------------------------------------------- Russian
    "ru": {
        "app.tagline": "Здоровье Mac в эпоху AI-разработки",
        "nav.overview": "Обзор",
        "nav.memory": "Память",
        "nav.processes": "Процессы",
        "nav.ai": "AI-инструменты",
        "nav.browser": "Браузер и блокировки",
        "nav.containers": "Контейнеры",
        "btn.rescan": "Обновить",
        "btn.fixall": "Исправить всё",
        "btn.fixall.n": "Исправить всё ({n})",
        "btn.quit": "Выход",
        "menu.open": "Открыть панель…",
        "btn.fix": "Исправить",
        "btn.working": "Выполняется…",
        "ui.vitals": "Показатели",
        "ui.free": "Свободно памяти",
        "ui.swap": "Подкачка",
        "ui.disk": "Свободно на диске",
        "ui.uptime": "Время работы",
        "ui.days": "дн.",
        "ui.recoverable": "Можно вернуть",
        "ui.findings": "Находки",
        "ui.nofindings": "Сообщать не о чем",
        "ui.allgood": "Сейчас этот Mac в хорошей форме.",
        "ui.nothing.section": "В этом разделе находок нет.",
        "ui.nofix": "Нет автоматического исправления",
        "ui.corehours": "{n} ядро-часов",
        "ui.scanning": "Сканирование…",
        "ui.stopped": "macpulse остановлен.",
        "ui.closetab": "Эту вкладку можно закрыть.",
        "ui.applied": "Применено {done} из {total} исправлений.",
        "ui.failed": "Не удалось применить: {err}",
        "ui.scanfail": "Сканирование не удалось: {err}",
        "ui.readonly": "Ничего не меняется, пока вы не нажмёте «Исправить»",
        "ui.confirm": "Применить эти исправления? Процессы будут остановлены.",
        "grade.healthy": "В порядке",
        "grade.attention": "Требует внимания",
        "grade.struggling": "В тяжёлом состоянии",
        "fix.stop.one": "Остановить PID {pid}",
        "fix.stop.many": "Остановить процессов: {n}",
        "fix.clearlock": "Очистить блокировку {app}",
        "fix.quitdocker": "Закрыть Docker Desktop",
        "res.stopped": "Остановлено {done} из {total} процессов",
        "res.cleared": "Удалено устаревших файлов блокировки для {app}: {n}",
        "res.dockerquit": "Docker Desktop закрыт",
        "res.dockerstuck": "Docker Desktop не закрылся — возможно, он о чём-то спрашивает",

        "cpu.t": "{name} сжёг {hours} ядро-часов",
        "cpu.d": "Работает {days} дн., постоянно занимая {pct}% ядра. При этом занимает "
                 "всего {size} памяти — именно поэтому чистильщики, смотрящие на размер, "
                 "его не видят. Цена — нагрев, батарея и подкачка, а не диск.",
        "ghost.t": "{name} всё ещё работает из {where}",
        "ghost.t.many": "{name} всё ещё работает из {where} (процессов: {n})",
        "ghost.where.volume": "тома, который больше не подключён",
        "ghost.where.app": "удалённого приложения",
        "ghost.d": "По пути {path} уже ничего нет, но процесс живёт {days} дн. и занимает "
                   "{size}. Деинсталлятор исчез вместе с приложением, поэтому никакая "
                   "очистка диска сюда не доберётся.",
        "ai.t": "Открыто сессий {host}: {n}, занимают {size}",
        "ai.d": "Каждая сессия поднимает собственный полный набор MCP-серверов вместо "
                "общего, поэтому расход умножается на число вкладок — примерно {each} на "
                "каждую. В Мониторинге системы это не видно одной строкой: расход "
                "размазан по десяткам мелких node-процессов.",
        "mcpdead.t": "MCP-сервер «{name}» настроен, но {verdict}",
        "mcpdead.d": "Он загружается в каждую AI-сессию, пытается запуститься и каждый раз "
                     "падает — сейчас в {n} сессиях. Либо авторизуйте его, либо уберите из "
                     "глобального конфига.",
        "mcp.unauth": "возвращает HTTP {code} — нет авторизации",
        "mcp.unreachable": "недоступен",
        "mcpcost.t": "MCP-сервер «{name}» занимает {size} в {n} процессах",
        "mcpcost.d": "stdio-серверы MCP запускаются по разу на сессию. Если держать много "
                     "AI-вкладок, умножьте это на их число.",
        "headless.t": "Осталось headless-браузеров от автоматизации: {n}",
        "headless.d": "Их запустил скрипт, который так и не закрыл их — самый старый "
                      "работает {days} дн. Они занимают {size}, держат открытым порт "
                      "отладки и могут заблокировать профиль так, что настоящий браузер "
                      "не запустится.",
        "lock.t": "{app} удерживается устаревшей блокировкой (мёртвый PID {pid})",
        "lock.d": "Блокировка указывает на несуществующий процесс — осталась после "
                  "принудительного завершения. Пока её не удалить, приложение может не "
                  "запускаться, обычно молча или с ошибкой -1712.",
        "docker.t": "Docker Desktop работает без контейнеров ({size})",
        "docker.d": "Docker держит запущенной виртуальную машину Linux независимо от того, "
                    "работает ли в ней что-нибудь. При нуле контейнеров эта память не даёт "
                    "ничего.",
        "sim.t": "Процессов iOS Simulator: {n}, занимают {size}",
        "sim.d": "Симуляторы продолжают работать после закрытия Xcode.",
        "swap.t": "{used} ГБ памяти вытеснено на диск (в этом Mac {ram} ГБ ОЗУ)",
        "swap.d": "Такая подкачка значит, что запущенным программам нужно больше памяти, чем есть в Mac, и каждое переключение ждёт диск. Сама она не уменьшится: закройте самую большую программу из списка или перезагрузитесь — Mac работает {days} дн.",
        "pressure.t": "Свободно всего {pct}% памяти",
        "pressure.d": "Ниже примерно четверти свободной памяти macOS начинает активно "
                      "сжимать и выгружать, и всё становится медленным — именно это "
                      "состояние заканчивается окном «системе не хватает памяти».",
        "disk.t": "На диске свободно всего {free} ГБ",
        "disk.d": "Когда ОЗУ не хватает, macOS выгружает память на диск (сейчас {swap} ГБ). Если диск так заполнен, выгружать некуда, и macOS начинает принудительно закрывать программы — это и есть окно «системе не хватает памяти». Сначала освободите место; самые крупные восстановимые объекты перечислены ниже.",
        "hog.t": "{name} занимает {size} — {pct}% от {ram} ГБ этого Mac",
        "hog.d": "Одна программа с таким объёмом памяти вытесняет всё остальное в подкачку. Если при запуске ей столько не требовалось, перезапуск вернёт память.",
        "hog.browser.d": "Почти всегда дело в одной-двух вкладках, а не в самом браузере. Откройте диспетчер задач браузера (Shift+Esc в Chrome), отсортируйте по памяти и закройте верхнюю вкладку. Перезапуск тоже помогает — вкладки вернутся, память освободится.",
        "uptime.t": "Работает {days} дн., подкачка под давлением",
        "uptime.d": "Долгое время работы само по себе не проблема, но вместе с заполненной "
                    "подкачкой перезагрузка — самый дешёвый полный сброс.",
        "swarm.t": "Копий {name}: {n}, занимают {size}",
        "swarm.d": "Вспомогательные процессы нормальны для браузеров и редакторов. "
                   "Показано, чтобы было видно, куда ушла память, а не потому что это "
                   "ошибка.",
    },
}


def t(lang, key, **params):
    """Look up a key, falling back to English, then to the key itself."""
    table = STRINGS.get(lang) or STRINGS[FALLBACK]
    template = table.get(key) or STRINGS[FALLBACK].get(key) or key
    try:
        return template.format(**params) if params else template
    except (KeyError, IndexError):
        return template


def bundle(lang):
    """The subset the web UI needs, merged over English so nothing renders blank."""
    merged = dict(STRINGS[FALLBACK])
    merged.update(STRINGS.get(lang) or {})
    return {k: v for k, v in merged.items()
            if k.startswith(("ui.", "btn.", "nav.", "grade.", "app.", "menu."))}
