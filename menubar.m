// macpulse menu bar agent.
//
// A Mac health tool belongs in the menu bar, not in a browser tab you have to remember
// to open. This is the shell; the Python engine remains the brain. The agent runs
// `macpulse --json`, shows the score where the user already looks, and interrupts only
// when the machine actually got worse.
//
// Written in Objective-C rather than Swift on purpose. This binary is compiled on the
// end user's own machine at install time — which is what avoids the Gatekeeper problem,
// since a locally built binary is never quarantined — so the build has to succeed on
// whatever toolchain that machine happens to have. On this very Mac `swiftc` cannot
// compile `print("hi")`: the Command Line Tools ship a Swift 6.1.2 compiler against an
// SDK whose .swiftinterface needs a newer one. clang has no equivalent failure mode.
//
//   clang -fobjc-arc -O2 -framework AppKit -o macpulse-menubar menubar.m

#import <AppKit/AppKit.h>
#import <sys/file.h>
#import <sys/mount.h>
#import <sys/sysctl.h>

// Clicking the app icon a second time must not start a second agent. macOS only
// enforces one-instance-per-bundle when an app is launched through Launch Services,
// and this one gets launched every which way — a Desktop alias, `open -a`, the binary
// directly. An exclusive lock on a file in Application Support holds regardless of how
// we were started. The second instance does not just die quietly either: it tells the
// live one to drop its menu open, so a click always produces something visible.
static NSString *const kShowNotification = @"io.macpulse.agent.show";

static BOOL AcquireSingleInstanceLock(void) {
    NSString *dir = [NSHomeDirectory() stringByAppendingPathComponent:
                     @"Library/Application Support/macpulse"];
    [[NSFileManager defaultManager] createDirectoryAtPath:dir
                             withIntermediateDirectories:YES attributes:nil error:NULL];
    NSString *lockPath = [dir stringByAppendingPathComponent:@"agent.lock"];
    int fd = open(lockPath.fileSystemRepresentation, O_CREAT | O_RDWR, 0600);
    if (fd < 0) return YES;                 // cannot lock: better to run than to refuse
    if (flock(fd, LOCK_EX | LOCK_NB) != 0) {
        close(fd);
        return NO;
    }
    return YES;                             // fd stays open on purpose: it IS the lock
}

static const NSTimeInterval kRefreshInterval = 15 * 60;
static const NSInteger kDropThatMatters = 12;   // score drop worth a notification

// The full scan runs every 15 minutes, which is too slow for the failure that matters
// most: RAM spills into swap, swap fills the disk, and macOS starts force-quitting apps.
// On 17 Sep 2026 that happened between two scans. So a sentinel reads two kernel
// counters every minute — no process spawned, effectively free — and triggers a full
// scan the moment either crosses a threshold. Thresholds mirror DISK_*_GB and
// SWAP_*_RATIO in the Python engine; change them together.
static const NSTimeInterval kSentinelInterval = 60;
static const double kDiskCriticalGB = 5, kDiskWarnGB = 15;
static const double kSwapWarnRatio = 0.5, kSwapCriticalRatio = 1.0;
static const NSTimeInterval kRenotifyAfter = 60 * 60;  // same problem, at most hourly

static NSInteger VitalLevel(void) {
    struct xsw_usage sw = {0};
    size_t len = sizeof(sw);
    sysctlbyname("vm.swapusage", &sw, &len, NULL, 0);
    uint64_t ram = 0;
    len = sizeof(ram);
    sysctlbyname("hw.memsize", &ram, &len, NULL, 0);
    double freeGB = 1e9;
    struct statfs fs;
    if (statfs("/System/Volumes/Data", &fs) == 0) {
        freeGB = (double)fs.f_bavail * (double)fs.f_bsize / 1073741824.0;
    }
    double ratio = ram ? (double)sw.xsu_used / (double)ram : 0;
    if (freeGB < kDiskCriticalGB || ratio >= kSwapCriticalRatio) return 2;
    if (freeGB < kDiskWarnGB || ratio >= kSwapWarnRatio) return 1;
    return 0;
}

static NSInteger SeverityRank(NSString *sev) {
    if ([sev isEqualToString:@"critical"]) return 2;
    if ([sev isEqualToString:@"warn"]) return 1;
    return 0;
}

// Memory and disk warnings are worth hearing about while they are still warnings —
// that is the whole point of seeing them early. Everything else speaks up only once it
// is critical, so the menu bar stays quiet about things that can wait.
static BOOL EarlyWarningKey(NSString *key) {
    return [key isEqualToString:@"disk"] || [key isEqualToString:@"swap"]
        || [key hasPrefix:@"hog:"] || [key isEqualToString:@"pressure"];
}

// The CLI is looked up in one place so that tests (and a user with a non-standard
// install) can point the agent at another build through MACPULSE_BIN.
static NSString *BinaryPath(void) {
    const char *env = getenv("MACPULSE_BIN");
    if (env && env[0]) return [NSString stringWithUTF8String:env];
    return [NSHomeDirectory() stringByAppendingPathComponent:@".local/bin/macpulse"];
}

// A scan that could not measure everything must not look like a clean bill of health.
// `complete` is false when a check raised; a payload from an older CLI has no such key
// and is treated as complete.
static BOOL ScanIsComplete(NSDictionary *payload) {
    id c = payload[@"complete"];
    return ![c isKindOfClass:NSNumber.class] || [c boolValue];
}

// The status-item text, as plain characters. Both the live menu bar and --print-title
// go through this one function, so what the test prints is what the user sees.
static NSString *TitleForPayload(NSDictionary *payload) {
    if (![payload isKindOfClass:NSDictionary.class] || !payload[@"score"]) return @"  ?";
    return [NSString stringWithFormat:@"◍ %ld%@", (long)[payload[@"score"] integerValue],
            ScanIsComplete(payload) ? @"" : @"?"];
}

static NSDictionary *RunScan(BOOL loginShell) {
    NSTask *task = [NSTask new];
    task.executableURL = [NSURL fileURLWithPath:@"/bin/bash"];
    task.arguments = @[loginShell ? @"-lc" : @"-c",
        [NSString stringWithFormat:@"'%@' --json 2>/dev/null", BinaryPath()]];
    NSPipe *pipe = [NSPipe pipe];
    task.standardOutput = pipe;
    task.standardError = [NSFileHandle fileHandleWithNullDevice];
    NSData *data = nil;
    if ([task launchAndReturnError:NULL]) {
        data = [pipe.fileHandleForReading readDataToEndOfFile];
        [task waitUntilExit];
    }
    id obj = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:NULL] : nil;
    return [obj isKindOfClass:NSDictionary.class] ? obj : nil;
}

@interface MPAgent : NSObject <NSApplicationDelegate>
@property (strong) NSStatusItem *item;
@property (strong) NSTimer *timer;
@property (strong) NSTimer *sentinelTimer;
@property (assign) NSInteger lastVitalLevel;
@property (strong) NSMutableDictionary<NSString *, NSNumber *> *lastRank;
@property (strong) NSMutableDictionary<NSString *, NSDate *> *notifiedAt;
@property (strong) NSDictionary *strings;
@property (assign) NSInteger lastScore;
@property (assign) BOOL busy;
@property (assign) BOOL introduced;
@property (copy) NSString *vitals;
@property (copy) NSString *partialNote;    // set when the last scan was incomplete
@property (copy) NSString *topReason;      // the largest score deduction, if reported
@end

@implementation MPAgent

- (NSString *)binary { return BinaryPath(); }

- (NSString *)s:(NSString *)key fallback:(NSString *)fallback {
    NSString *v = self.strings[key];
    return (v.length > 0) ? v : fallback;
}

- (NSColor *)colourFor:(NSInteger)score {
    if (score >= 85) return [NSColor systemGreenColor];
    if (score >= 65) return [NSColor systemOrangeColor];
    return [NSColor systemRedColor];
}

- (void)start {
    [NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];
    self.lastScore = -1;
    self.lastRank = [NSMutableDictionary new];
    // Persisted, so quitting and reopening the agent does not repeat an alert the user
    // saw a minute ago. Entries older than the re-notify window are dropped on load.
    self.notifiedAt = [NSMutableDictionary new];
    NSDictionary *saved = [[NSUserDefaults standardUserDefaults] dictionaryForKey:@"notifiedAt"];
    for (NSString *key in saved) {
        NSDate *when = [saved[key] isKindOfClass:NSDate.class] ? saved[key] : nil;
        if (when && -[when timeIntervalSinceNow] < kRenotifyAfter) {
            self.notifiedAt[key] = when;
            self.lastRank[key] = @1;     // already announced: only an escalation speaks
        }
    }
    self.item = [[NSStatusBar systemStatusBar]
                 statusItemWithLength:NSVariableStatusItemLength];
    self.item.button.title = @"  –";
    [[NSDistributedNotificationCenter defaultCenter]
        addObserver:self selector:@selector(popMenu)
               name:kShowNotification object:nil];
    [self refresh];
    self.timer = [NSTimer scheduledTimerWithTimeInterval:kRefreshInterval
                                                 target:self
                                               selector:@selector(refresh)
                                               userInfo:nil
                                                repeats:YES];
    self.sentinelTimer = [NSTimer scheduledTimerWithTimeInterval:kSentinelInterval
                                                         target:self
                                                       selector:@selector(sentinel)
                                                       userInfo:nil
                                                        repeats:YES];
}

- (void)sentinel {
    NSInteger level = VitalLevel();
    // Only a change for the worse earns an unscheduled scan. If a scan is already
    // running, keep the old level so the next tick tries again instead of losing it.
    if (level > self.lastVitalLevel) {
        if (self.busy) return;
        [self refresh];
    }
    self.lastVitalLevel = level;
}

// The menu bar is a glance, not a dashboard: one coloured pulse glyph and a number.
- (void)renderTitle:(NSInteger)score complete:(BOOL)complete {
    NSMutableAttributedString *full = [NSMutableAttributedString new];
    [full appendAttributedString:
        [[NSAttributedString alloc] initWithString:@"◍ "
            attributes:@{NSForegroundColorAttributeName: [self colourFor:score],
                         NSFontAttributeName: [NSFont systemFontOfSize:11]}]];
    [full appendAttributedString:
        [[NSAttributedString alloc] initWithString:[NSString stringWithFormat:@"%ld%@", (long)score, complete ? @"" : @"?"]
            attributes:@{NSFontAttributeName:
                [NSFont monospacedDigitSystemFontOfSize:12 weight:NSFontWeightMedium]}]];
    self.item.button.attributedTitle = full;
}

- (void)refresh {
    if (self.busy) return;
    self.busy = YES;
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
        NSDictionary *payload = RunScan(YES);
        dispatch_async(dispatch_get_main_queue(), ^{
            [self apply:payload];
            self.busy = NO;
        });
    });
}

- (void)apply:(NSDictionary *)payload {
    if (![payload isKindOfClass:NSDictionary.class] || !payload[@"score"]) {
        self.item.button.title = @"  ?";
        [self buildMenuWithScore:-1 grade:@"macpulse unavailable" findings:@[]];
        return;
    }
    NSInteger score = [payload[@"score"] integerValue];
    if ([payload[@"strings"] isKindOfClass:NSDictionary.class]) {
        self.strings = payload[@"strings"];
    }
    NSString *grade = payload[@"grade"] ?: @"";
    NSDictionary *m = [payload[@"memory"] isKindOfClass:NSDictionary.class] ? payload[@"memory"] : nil;
    if (m) {
        NSString *swapLabel = [self s:@"ui.swap" fallback:@"Swap"];
        NSString *diskLabel = [self s:@"ui.disk" fallback:@"Disk free"];
        self.vitals = [NSString stringWithFormat:@"%@ %.1f GB · %@ %.0f GB",
                       swapLabel, [m[@"swap_used_mb"] doubleValue] / 1024.0,
                       diskLabel, [m[@"disk_free"] doubleValue] / 1073741824.0];
    }
    NSArray *findings = [payload[@"findings"] isKindOfClass:NSArray.class]
                        ? payload[@"findings"] : @[];

    BOOL complete = ScanIsComplete(payload);
    self.partialNote = nil;
    if (!complete) {
        NSDictionary *checks = [payload[@"checks"] isKindOfClass:NSDictionary.class]
                               ? payload[@"checks"] : nil;
        NSArray *failed = [checks[@"failed"] isKindOfClass:NSArray.class] ? checks[@"failed"] : @[];
        NSString *names = failed.count ? [failed componentsJoinedByString:@", "] : @"unknown";
        self.partialNote = [NSString stringWithFormat:
            @"partial scan — could not measure: %@", names];
    }
    self.topReason = nil;
    NSInteger best = 0;
    if ([payload[@"score_breakdown"] isKindOfClass:NSArray.class]) {
        for (NSDictionary *row in payload[@"score_breakdown"]) {
            if (![row isKindOfClass:NSDictionary.class]) continue;
            NSInteger pts = [row[@"points"] integerValue];
            if (pts > best && [row[@"reason"] isKindOfClass:NSString.class]) {
                best = pts;
                self.topReason = [NSString stringWithFormat:@"−%ld  %@", (long)pts, row[@"reason"]];
            }
        }
    }

    [self renderTitle:score complete:complete];
    [self buildMenuWithScore:score grade:grade findings:findings];

    if (!self.introduced) {
        self.introduced = YES;
        [self popMenu];             // first launch: show the user where it went
    }

    // Only speak up when something got worse. A tool that notifies on every scan is
    // muted by the user within a day, and then never heard from again. So: one
    // notification per problem when it appears or escalates, naming the problem and
    // what to do about it, and not again for the same problem within the hour.
    BOOL spoke = NO;
    NSMutableDictionary *ranks = [NSMutableDictionary new];
    NSDate *now = [NSDate date];
    for (NSDictionary *f in findings) {
        NSString *key = [f[@"key"] isKindOfClass:NSString.class] ? f[@"key"] : nil;
        if (!key) continue;
        NSInteger rank = SeverityRank(f[@"severity"]);
        ranks[key] = @(rank);
        NSInteger before = [self.lastRank[key] integerValue];
        NSInteger bar = EarlyWarningKey(key) ? 1 : 2;
        NSDate *last = self.notifiedAt[key];
        BOOL fresh = !last || [now timeIntervalSinceDate:last] > kRenotifyAfter;
        if (rank >= bar && rank > before && fresh) {
            [self notify:f[@"detail"] ?: @"" subtitle:f[@"title"] ?: @""];
            self.notifiedAt[key] = now;
            spoke = YES;
        }
    }
    self.lastRank = ranks;
    if (spoke) {
        [[NSUserDefaults standardUserDefaults] setObject:self.notifiedAt forKey:@"notifiedAt"];
    }
    if (!spoke && self.lastScore >= 0 && (self.lastScore - score) >= kDropThatMatters) {
        [self notify:grade subtitle:[NSString stringWithFormat:@"%ld → %ld",
                                     (long)self.lastScore, (long)score]];
    }
    self.lastScore = score;
}

- (void)buildMenuWithScore:(NSInteger)score grade:(NSString *)grade findings:(NSArray *)findings {
    NSMenu *menu = [NSMenu new];
    NSString *headText = (score >= 0)
        ? [NSString stringWithFormat:@"%ld/100 — %@", (long)score, grade] : grade;
    NSMenuItem *head = [[NSMenuItem alloc] initWithTitle:headText action:nil keyEquivalent:@""];
    head.enabled = NO;
    [menu addItem:head];

    for (NSString *note in @[self.partialNote ?: @"", self.topReason ?: @""]) {
        if (note.length == 0) continue;
        NSMenuItem *n = [[NSMenuItem alloc] initWithTitle:note action:nil keyEquivalent:@""];
        n.enabled = NO;
        n.attributedTitle = [[NSAttributedString alloc] initWithString:note
            attributes:@{NSFontAttributeName: [NSFont systemFontOfSize:11],
                         NSForegroundColorAttributeName: [NSColor secondaryLabelColor]}];
        [menu addItem:n];
    }

    // The two numbers this tool exists for, where a glance can reach them. Swap says
    // how much memory has spilled onto the disk; free space says how much room is left
    // for it to spill into. Either one alone hides the failure they cause together.
    if (self.vitals.length > 0) {
        NSMenuItem *v = [[NSMenuItem alloc] initWithTitle:self.vitals action:nil keyEquivalent:@""];
        v.enabled = NO;
        v.attributedTitle = [[NSAttributedString alloc] initWithString:self.vitals
            attributes:@{NSFontAttributeName: [NSFont monospacedDigitSystemFontOfSize:11
                                                weight:NSFontWeightRegular],
                         NSForegroundColorAttributeName: [NSColor secondaryLabelColor]}];
        [menu addItem:v];
    }

    if (findings.count > 0) {
        [menu addItem:[NSMenuItem separatorItem]];
        NSUInteger shown = MIN(findings.count, (NSUInteger)6);
        for (NSUInteger i = 0; i < shown; i++) {
            NSDictionary *f = findings[i];
            NSString *sev = f[@"severity"] ?: @"info";
            NSString *dot = [sev isEqualToString:@"critical"] ? @"●"
                          : ([sev isEqualToString:@"warn"] ? @"◆" : @"○");
            NSString *title = f[@"title"] ?: @"";
            if (title.length > 58) title = [[title substringToIndex:56] stringByAppendingString:@"…"];
            NSString *line = [NSString stringWithFormat:@"%@  %@", dot, title];
            // History earns its keep here: "this has been true for 4 days" is the one
            // thing a single scan can never tell you.
            double age = [f[@"age_days"] doubleValue];
            if (age >= 1) line = [line stringByAppendingFormat:@"  (%dd)", (int)age];
            NSMenuItem *mi = [[NSMenuItem alloc] initWithTitle:line
                                                        action:@selector(openPanel)
                                                 keyEquivalent:@""];
            mi.target = self;
            [menu addItem:mi];
        }
    }

    [menu addItem:[NSMenuItem separatorItem]];
    NSMenuItem *scan = [[NSMenuItem alloc] initWithTitle:[self s:@"btn.rescan" fallback:@"Rescan"]
                                                  action:@selector(refresh) keyEquivalent:@"r"];
    scan.target = self;
    [menu addItem:scan];
    NSMenuItem *panel = [[NSMenuItem alloc] initWithTitle:[self s:@"menu.open" fallback:@"Open panel…"]
                                                   action:@selector(openPanel) keyEquivalent:@"o"];
    panel.target = self;
    [menu addItem:panel];
    [menu addItem:[NSMenuItem separatorItem]];
    NSMenuItem *quit = [[NSMenuItem alloc] initWithTitle:[self s:@"btn.quit" fallback:@"Quit"]
                                                  action:@selector(quitNow) keyEquivalent:@"q"];
    quit.target = self;
    [menu addItem:quit];
    self.item.menu = menu;
}

// Opening the menu is what makes a click feel like it did something. Called on first
// launch and whenever a second launch attempt is folded into this instance.
- (void)popMenu {
    dispatch_async(dispatch_get_main_queue(), ^{
        [self.item.button performClick:nil];
    });
}

// Clicking the icon of an app that is ALREADY running does not start a new process —
// Launch Services just activates the existing one. For a menu bar app with no windows
// that looks exactly like nothing happened, which is what the first version did. This
// is the hook macOS provides for that reopen, and it is the one that actually fires.
- (BOOL)applicationShouldHandleReopen:(NSApplication *)sender
                    hasVisibleWindows:(BOOL)visible {
    [self popMenu];
    return NO;
}

- (void)openPanel {
    NSTask *task = [NSTask new];
    task.executableURL = [NSURL fileURLWithPath:@"/bin/bash"];
    task.arguments = @[@"-lc",
        [NSString stringWithFormat:@"'%@' --ui --port 7745 >/dev/null 2>&1 &", [self binary]]];
    [task launchAndReturnError:NULL];
}

- (NSString *)appleScriptString:(NSString *)text {
    // Finding titles routinely contain quotes and apostrophes; an unescaped one turns
    // the AppleScript into a syntax error and the notification silently never appears.
    NSString *safe = [text stringByReplacingOccurrencesOfString:@"\\" withString:@"\\\\"];
    safe = [safe stringByReplacingOccurrencesOfString:@"\"" withString:@"\\\""];
    // A raw line break inside a quoted AppleScript string is a syntax error too, and
    // finding text carries process and file names, which may contain one.
    safe = [safe stringByReplacingOccurrencesOfString:@"\r" withString:@" "];
    return [safe stringByReplacingOccurrencesOfString:@"\n" withString:@" "];
}

- (void)notify:(NSString *)body subtitle:(NSString *)subtitle {
    NSString *script = [NSString stringWithFormat:
        @"display notification \"%@\" with title \"macpulse\" subtitle \"%@\"",
        [self appleScriptString:body], [self appleScriptString:subtitle]];
    NSTask *task = [NSTask new];
    task.executableURL = [NSURL fileURLWithPath:@"/usr/bin/osascript"];
    task.arguments = @[@"-e", script];
    [task launchAndReturnError:NULL];
}

- (void)quitNow { [NSApp terminate:nil]; }

@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        // Headless mode for tests and scripts: run the CLI, print the title the status
        // item would carry, leave. No NSApplication, no status item, no instance lock.
        if (argc > 1 && strcmp(argv[1], "--print-title") == 0) {
            NSDictionary *payload = RunScan(NO);
            NSString *title = TitleForPayload(payload);
            printf("%s\n", title.UTF8String);
            return payload ? 0 : 1;
        }
        if (!AcquireSingleInstanceLock()) {
            // Already running. Ask that instance to show itself, then step aside.
            [[NSDistributedNotificationCenter defaultCenter]
                postNotificationName:kShowNotification object:nil userInfo:nil
                  deliverImmediately:YES];
            return 0;
        }
        NSApplication *app = [NSApplication sharedApplication];
        MPAgent *agent = [MPAgent new];
        app.delegate = agent;          // must be set before run: reopen arrives via it
        [agent start];
        [NSApp run];
    }
    return 0;
}
