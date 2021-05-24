import os
import sublime
import sublime_plugin
import subprocess

st_encodings_trans = {
   "UTF-8" : "utf-8",
   "UTF-8 with BOM" : "utf-8-sig",
   "UTF-16 LE" : "utf-16-le",
   "UTF-16 LE with BOM" : "utf-16",
   "UTF-16 BE" : "utf-16-be",
   "UTF-16 BE with BOM" : "utf-16",
   "Western (Windows 1252)" : "cp1252",
   "Western (ISO 8859-1)" : "iso8859-1",
   "Western (ISO 8859-3)" : "iso8859-3",
   "Western (ISO 8859-15)" : "iso8859-15",
   "Western (Mac Roman)" : "mac-roman",
   "DOS (CP 437)" : "cp437",
   "Arabic (Windows 1256)" : "cp1256",
   "Arabic (ISO 8859-6)" : "iso8859-6",
   "Baltic (Windows 1257)" : "cp1257",
   "Baltic (ISO 8859-4)" : "iso8859-4",
   "Celtic (ISO 8859-14)" : "iso8859-14",
   "Central European (Windows 1250)" : "cp1250",
   "Central European (ISO 8859-2)" : "iso8859-2",
   "Cyrillic (Windows 1251)" : "cp1251",
   "Cyrillic (Windows 866)" : "cp866",
   "Cyrillic (ISO 8859-5)" : "iso8859-5",
   "Cyrillic (KOI8-R)" : "koi8-r",
   "Cyrillic (KOI8-U)" : "koi8-u",
   "Estonian (ISO 8859-13)" : "iso8859-13",
   "Greek (Windows 1253)" : "cp1253",
   "Greek (ISO 8859-7)" : "iso8859-7",
   "Hebrew (Windows 1255)" : "cp1255",
   "Hebrew (ISO 8859-8)" : "iso8859-8",
   "Nordic (ISO 8859-10)" : "iso8859-10",
   "Romanian (ISO 8859-16)" : "iso8859-16",
   "Turkish (Windows 1254)" : "cp1254",
   "Turkish (ISO 8859-9)" : "iso8859-9",
   "Vietnamese (Windows 1258)" :  "cp1258",
   "Hexadecimal" : None,
   "Undefined" : None
}

os_is_windows = os.name == 'nt'
default_binary = 'clang-format.exe' if os_is_windows else 'clang-format'

languages = ['C', 'C++']

def load_settings():
    # We set these globals.
    global format_on_save
    settings_local = sublime.active_window().active_view().settings().get('ClangFormat2', {})
    load = lambda name, default: settings_local.get(name, default)
    # Load settings, with defaults.
    format_on_save = load('format_on_save', False)

def is_supported(lang):
    load_settings()
    return any((lang.endswith((l + '.tmLanguage', l + '.sublime-syntax')) for l in languages))

def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None

def check_binary():
    if which(default_binary) == None:
        return False
    return True

def has_clang_format_file_in_parents(filename):
    f = filename
    while f != os.path.dirname(f):
        f = os.path.dirname(f)
        if os.path.exists(os.path.join(f, ".clang-format")):
            return True
    return False

class ClangFormat2Command(sublime_plugin.TextCommand):
    def run(self, edit):
        if self.view.file_name() == None:
            sublime.status_message("clang_format2: file not saved")
            return

        if not has_clang_format_file_in_parents(self.view.file_name()):
            sublime.status_message("clang_format2: no .clang-format file found")
            return

        if not check_binary():
            sublime.status_message("clang_format2: The clang-format binary was not found")
            return

        encoding = st_encodings_trans[self.view.encoding()]
        if encoding is None:
            encoding = 'utf-8'

        command = [default_binary, '-style', 'file']
        command.extend(['-assume-filename', str(self.view.file_name())] )

        buf = self.view.substr(sublime.Region(0, self.view.size()))
        startupinfo = None
        if os_is_windows:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE,
                             startupinfo=startupinfo)
        output, error = p.communicate(buf.encode(encoding))

        # Display any errors returned by clang-format using a message box,
        # instead of just printing them to the console. Also, we halt on all
        # errors: e.g. We don't just settle for using using a default style.
        if error:
            # We don't want to do anything by default.
            # If the error message tells us it is doing that, truncate it.
            default_message = ", using LLVM style"
            msg = error.decode("utf-8")
            if msg.strip().endswith(default_message):
                msg = msg[:-len(default_message)-1]
            sublime.error_message("Clang format: " + msg)
            # Don't do anything.
            return

        # If there were no errors, we replace the view with the outputted buf.
        # Temporarily disable tabs to space so that tabs elsewhere in the file
        # do not get modified if they were not part of the formatted selection
        prev_tabs_to_spaces = self.view.settings().get('translate_tabs_to_spaces')
        self.view.settings().set('translate_tabs_to_spaces', False)

        self.view.replace(
            edit, sublime.Region(0, self.view.size()),
            output.decode(encoding))

        # Re-enable previous tabs to space setting
        self.view.settings().set('translate_tabs_to_spaces', prev_tabs_to_spaces)

class clangFormatEventListener(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        # Only do this for supported languages
        syntax = view.settings().get('syntax')
        if is_supported(syntax):
            # Ensure that settings are up to date.
            load_settings()
            if format_on_save:
                print("Auto-applying Clang Format on save.")
                view.run_command("clang_format2")
