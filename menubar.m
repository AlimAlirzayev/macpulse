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

static const NSTimeInterval kRefreshInterval = 15 * 60;
static const NSInteger kDropThatMatters = 12;   // score drop worth a notification

@interface MPAgent : NSObject
@property (strong) NSStatusItem *item;
@property (strong) NSTimer *timer;
@property (strong) NSDictionary *strings;
@property (assign) NSInteger lastScore;
@property (assign) BOOL busy;
@end

@implementation MPAgent

- (NSString *)binary {
    return [NSHomeDirectory() stringByAppendingPathComponent:@".local/bin/macpulse"];
}

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
    self.item = [[NSStatusBar systemStatusBar]
                 statusItemWithLength:NSVariableStatusItemLength];
    self.item.button.title = @"  –";
    [self refresh];
    self.timer = [NSTimer scheduledTimerWithTimeInterval:kRefreshInterval
                                                 target:self
                                               selector:@selector(refresh)
                                               userInfo:nil
                                                repeats:YES];
}

// The menu bar is a glance, not a dashboard: one coloured pulse glyph and a number.
- (void)renderTitle:(NSInteger)score {
    NSMutableAttributedString *full = [NSMutableAttributedString new];
    [full appendAttributedString:
        [[NSAttributedString alloc] initWithString:@"◍ "
            attributes:@{NSForegroundColorAttributeName: [self colourFor:score],
                         NSFontAttributeName: [NSFont systemFontOfSize:11]}]];
    [full appendAttributedString:
        [[NSAttributedString alloc] initWithString:[NSString stringWithFormat:@"%ld", (long)score]
            attributes:@{NSFontAttributeName:
                [NSFont monospacedDigitSystemFontOfSize:12 weight:NSFontWeightMedium]}]];
    self.item.button.attributedTitle = full;
}

- (void)refresh {
    if (self.busy) return;
    self.busy = YES;
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
        NSTask *task = [NSTask new];
        task.executableURL = [NSURL fileURLWithPath:@"/bin/bash"];
        task.arguments = @[@"-lc",
            [NSString stringWithFormat:@"'%@' --json 2>/dev/null", [self binary]]];
        NSPipe *pipe = [NSPipe pipe];
        task.standardOutput = pipe;
        task.standardError = [NSFileHandle fileHandleWithNullDevice];
        NSData *data = nil;
        if ([task launchAndReturnError:NULL]) {
            data = [pipe.fileHandleForReading readDataToEndOfFile];
            [task waitUntilExit];
        }
        NSDictionary *payload = data
            ? [NSJSONSerialization JSONObjectWithData:data options:0 error:NULL] : nil;
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
    NSArray *findings = [payload[@"findings"] isKindOfClass:NSArray.class]
                        ? payload[@"findings"] : @[];

    [self renderTitle:score];
    [self buildMenuWithScore:score grade:grade findings:findings];

    // Only speak up when the machine got meaningfully worse. A tool that notifies on
    // every scan is muted by the user within a day, and then never heard from again.
    if (self.lastScore >= 0 && (self.lastScore - score) >= kDropThatMatters) {
        [self notify:[NSString stringWithFormat:@"%ld → %ld · %@",
                      (long)self.lastScore, (long)score, grade]];
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

- (void)openPanel {
    NSTask *task = [NSTask new];
    task.executableURL = [NSURL fileURLWithPath:@"/bin/bash"];
    task.arguments = @[@"-lc",
        [NSString stringWithFormat:@"'%@' --ui --port 7745 >/dev/null 2>&1 &", [self binary]]];
    [task launchAndReturnError:NULL];
}

- (void)notify:(NSString *)body {
    // Finding titles routinely contain quotes and apostrophes; an unescaped one turns
    // the AppleScript into a syntax error and the notification silently never appears.
    NSString *safe = [body stringByReplacingOccurrencesOfString:@"\\" withString:@"\\\\"];
    safe = [safe stringByReplacingOccurrencesOfString:@"\"" withString:@"\\\""];
    NSString *script = [NSString stringWithFormat:
        @"display notification \"%@\" with title \"macpulse\"", safe];
    NSTask *task = [NSTask new];
    task.executableURL = [NSURL fileURLWithPath:@"/usr/bin/osascript"];
    task.arguments = @[@"-e", script];
    [task launchAndReturnError:NULL];
}

- (void)quitNow { [NSApp terminate:nil]; }

@end

int main(void) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        MPAgent *agent = [MPAgent new];
        [agent start];
        (void)app;
        [NSApp run];
    }
    return 0;
}
