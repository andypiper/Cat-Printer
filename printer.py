'Cat-Printer: Core driver'

import os
import io
import sys
import argparse
import subprocess
import asyncio
import platform

class ExitCodes():
    'Exit codes'
    Success = 0
    GeneralError = 1
    InvalidArgument = 2
    PrinterError = 64
    IncompleteProgram = 128
    MissingDependency = 129

def info(*args, **kwargs):
    'Just `print` to `stdout`'
    print(*args, **kwargs, file=sys.stdout, flush=True)

def error(*args, exception=None, **kwargs):
    '`print` to `stderr`, or optionally raise an exception'
    if exception is not None:
        raise exception(*args)
    else:
        print(*args, **kwargs, file=sys.stderr, flush=True)

def fatal(*args, code=ExitCodes.GeneralError, **kwargs):
    '`print` to `stderr`, and exit with `code`'
    print(*args, **kwargs, file=sys.stderr, flush=True)
    sys.exit(code)

# Do i18n first

try:
    from printer_lib.i18n import I18nLib
    for path in ('www/lang', 'lang'):
        if os.path.exists(path):
            I18n = I18nLib(path)
            break
    else:   # if didn't break
        error('Warning: No languages were found', exception=None)
except ImportError:
    fatal(
        'Folder "printer_lib" is incomplete or missing, please check.',
        code=ExitCodes.IncompleteProgram
    )

# Test if `pyobjc` is there on MacOS

if platform.system() == 'macOS':
    try:
        import CoreBluetooth    # pylint: disable=import-error,unused-import
    except ImportError:
        fatal(
            I18n['please-install-pyobjc-via-pip'],
            ' $ pip3 install pyobjc',
            code=ExitCodes.MissingDependency,
            sep='\n'
        )

# Test if `bleak` is there

try:
    from bleak import BleakClient, BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.exc import BleakError, BleakDBusError
except ImportError:
    fatal(
        I18n['please-install-bleak-via-pip'],
        ' $ pip3 install bleak',
        code=ExitCodes.MissingDependency,
        sep='\n'
    )

# Import essential basic parts

try:
    from printer_lib.models import Models, Model
    from printer_lib.commander import Commander, reverse_bits
    from printer_lib.text_print import TextCanvas
except ImportError:
    fatal(
        I18n['folder-printer_lib-is-incomplete-or-missing-please-check'],
        code=ExitCodes.IncompleteProgram
    )

# Helpers

def flip(buffer, width, height, horizontally=False, vertically=True, *, overwrite=False):
    'Flip the bitmap data'
    buffer.seek(0)
    if not horizontally and not vertically:
        return buffer
    data_width = width // 8
    result_0 = io.BytesIO()
    if horizontally:
        while data := buffer.read(data_width):
            data = bytearray(map(reverse_bits, data))
            data.reverse()
            result_0.write(data)
        result_0.seek(0)
    else:
        result_0 = buffer
    result_1 = io.BytesIO()
    if vertically:
        for i in range(height - 1, -1, -1):
            result_0.seek(i * data_width)
            data = result_0.read(data_width)
            result_1.write(data)
        result_1.seek(0)
    else:
        result_1 = result_0
    buffer.seek(0)
    if overwrite:
        while data := result_1.read(data_width):
            buffer.write(data)
        buffer.seek(0)
    return result_1


# Classes

class PrinterError(Exception):
    'Exception raised when something went wrong during printing'
    message: str
    message_localized: str
    def __init__(self, *args):
        super().__init__(*args)
        self.message = args[0]
        self.message_localized = I18n[args]

class PrinterData():
    ''' The image data to be used by `PrinterDriver`.
        Optionally give an io `file` to read PBM image data from it.
        To read the bitmap data, simply do `io` operation with attribute `data`
    '''

    buffer = 4 * 1024 * 1024

    width: int
    'Constant width'
    _data_width: int
    'Amount of data bytes per line'
    height: int
    'Total height of bitmap data'
    data: bytearray
    'Monochrome bitmap data `io`, of size `width * height // 8`'
    pages: list
    'Height of every page in a `list`'
    max_size: int
    'Max size of `data`'
    full: bool
    'Whether the data is full (i.e. have reached max size)'

    def __init__(self, width, file: io.BufferedIOBase=None, max_size=64 * 1024 * 1024):
        self.width = width
        self._data_width = width // 8
        self.height = 0
        self.max_size = max_size
        self.max_height = max_size // self._data_width
        self.full = False
        self.data = io.BytesIO()
        self.pages = []
        if file is not None:
            self.from_pbm(file)

    def write(self, data: bytearray):
        ''' Directly write bitmap data to `data` directly. For memory safety,
            will overwrite earliest data if going to reach `max_size`.
            returns the io position after writing.
        '''
        data_len = len(data)
        if self.data.tell() + data_len > self.max_size:
            self.full = True
            self.data.seek(0)
        self.data.write(data)
        position = self.data.tell()
        if not self.full:
            self.height = position // self._data_width
        return position

    def read(self, length=-1):
        ''' Read the bitmap data entirely, in chunks.
            `yield` the resulting data.
            Will finally put seek point to `0`
        '''
        self.data.seek(0)
        while chunk := self.data.read(length):
            yield chunk
        self.data.seek(0)

    def from_pbm(self, file: io.BufferedIOBase):
        ''' Read from buffer `file` that have PBM image data.
            Concatenating multiple files *is* allowed.
            Calling multiple times is also possible,
            before or after yielding `read`, not between.
            Will put seek point to last byte written.
        '''
        while signature := file.readline():
            if signature != b'P4\n':
                error('input-is-not-pbm-image', exception=PrinterError)
            while True:
                # There can be comments. Skip them
                line = file.readline()[0:-1]
                if line[0:1] != b'#':
                    break
            width, height = map(int, line.split(b' '))
            if width != self.width:
                error(
                    'unsuitable-image-width-expected-0-got-1',
                    self.width, width,
                    exception=PrinterError
                )
            self.pages.append(height)
            self.height += height
            total_size = 0
            expected_size = self._data_width * height
            while raw_data := file.read(
                    min(self.buffer, expected_size - total_size)):
                total_size += len(raw_data)
                self.write(raw_data)
                if self.full:
                    self.pages.pop(0)
            if total_size != expected_size:
                error('broken-pbm-image', exception=PrinterError)
        if file is not sys.stdin.buffer:
            file.close()

    def to_pbm(self, *, merge_pages=False):
        ''' `yield` the pages as PBM image data,
            optionally just merge to one page.
            Will restore the previous seek point.
        '''
        pointer = self.data.tell()
        self.data.seek(0)
        if merge_pages:
            yield bytearray(
                b'P4\n%i %i\n' % (self.width, self.height)
            ) + self.data.read()
        else:
            for i in self.pages:
                yield bytearray(
                    b'P4\n%i %i\n' % (self.width, i)
                ) + self.data.read(self._data_width * i)
        self.data.seek(pointer)

    def __del__(self):
        self.data.truncate(0)
        self.data.close()
        del self.data

# The driver

class PrinterDriver(Commander):
    'The core driver of Cat-Printer'

    device: BleakClient = None
    'The connected printer device.'

    model: Model = None
    'The printer model'

    scan_timeout: float = 4.0

    connection_timeout : float = 5.0

    use_text_mode: bool = False
    font_family: str = 'font'

    text_canvas: TextCanvas = None
    flip_h: bool = False
    flip_v: bool = False
    wrap: bool = False
    rtl: bool = False

    mtu: int = 200

    tx_characteristic = '0000ae01-0000-1000-8000-00805f9b34fb'
    rx_characteristic = '0000ae02-0000-1000-8000-00805f9b34fb'

    dry_run: bool = False
    'Test print process only, will not waste paper'

    fake: bool = False
    'Test data logic only, will not waste time'

    dump: bool = False
    'Dump traffic data, and if it\'s text printing, the resulting PBM image'

    _loop: asyncio.AbstractEventLoop = None

    _traffic_dump: io.FileIO = None

    _paused: bool = False

    _pending_data: io.BytesIO = None

    def __init__(self):
        self._loop = asyncio.get_event_loop_policy().get_event_loop()

    def loop(self, *futures):
        ''' Run coroutines in order in current event loop until complete,
            return its result directly, or their result as tuple
        '''
        results = []
        for future in futures:
            results.append(self._loop.run_until_complete(future))
        return results[0] if len(results) == 1 else tuple(results)

    def connect(self, name=None, address=None):
        ''' Connect to this device, and operate on it
        '''
        self._pending_data = io.BytesIO()
        if self.fake:
            return
        if (self.device is not None and address is not None and
            (self.device.address.lower() == address.lower())):
            return
        try:
            if self.device is not None and self.device.is_connected:
                self.loop(self.device.stop_notify(self.rx_characteristic))
                self.loop(self.device.disconnect())
        except:     # pylint: disable=bare-except
            pass
        finally:
            self.device = None
        if name is None and address is None:
            return
        self.model = Models[name]
        self.device = BleakClient(address)
        def notify(_char, data):
            if data == b'\x51\x78\xae\x01\x01\x00\x10\x70\xff':
                self._paused = True
            elif data == b'\x51\x78\xae\x01\x01\x00\x00\x00\xff':
                self._paused = False
        self.loop(
            self.device.connect(timeout=self.connection_timeout),
            self.device.start_notify(self.rx_characteristic, notify)
        )

    def scan(self, identifier: str=None, *, use_result=False):
        ''' Scan for supported devices, optionally filter with `identifier`,
            which can be device model (bluetooth name), and optionally MAC address, after a comma.
            If `use_result` is True, connect to the first available device to driver instantly.
            Note: MAC address doesn't work on Apple MacOS. In place with it,
            You need an UUID of BLE device dynamically given by MacOS.
        '''
        if self.fake:
            return
        if identifier:
            if identifier.find(',') != -1:
                name, address = identifier.split(',')
                if name not in Models:
                    error('model-0-is-not-supported-yet', name, exception=PrinterError)
                if address[2::3] != ':::::' and len(address.replace('-', '')) != 32:
                    error('invalid-address-0', address, exception=PrinterError)
                if use_result:
                    self.connect(name, address)
                return [BLEDevice(address, name)]
            elif (identifier not in Models and
                identifier[2::3] != ':::::' and len(identifier.replace('-', '')) != 32):
                error('model-0-is-not-supported-yet', identifier, exception=PrinterError)
        # scanner = BleakScanner()
        devices = [x for x in self.loop(
            BleakScanner.discover(self.scan_timeout)
        ) if x.name in Models]
        if identifier is not None:
            if identifier in Models:
                devices = [dev for dev in devices if dev.name == identifier]
            else:
                devices = [dev for dev in devices if dev.address.lower() == identifier.lower()]
        if use_result and len(devices) != 0:
            self.connect(devices[0].name, devices[0].address)
        return devices

    def print(self, file: io.BufferedIOBase, *, mode='default',
              identifier: str=None):
        ''' Print data of `file`.
            Currently, available modes are `pbm` and `text`.
            If no devices were connected, scan & connect to one first.
        '''
        self._pending_data = io.BytesIO()
        if self.device is None:
            self.scan(identifier, use_result=True)
        if self.device is None and not self.fake:
            error('no-available-devices-found', exception=PrinterError)
        if mode == 'pbm' or mode == 'default':
            printer_data = PrinterData(self.model.paper_width, file)
            self._print_bitmap(printer_data)
        elif mode == 'text':
            self._print_text(file)
        else:
            ... # TODO: other?

    def flush(self):
        'Send pending data instantly, but will block if paused'
        self._pending_data.seek(0)
        while chunk := self._pending_data.read(self.mtu):
            while self._paused:
                self.loop(asyncio.sleep(0.2))
            self.loop(
                self.device.write_gatt_char(self.tx_characteristic, chunk),
                asyncio.sleep(0.02)
            )
        self._pending_data.seek(0)
        self._pending_data.truncate()

    def send(self, data):
        ''' Pend `data`, send if enough size is reached.
            You can manually `flush` to send data instantly,
            and should do `flush` at the end of printing.
        '''
        if self.dump:
            if self._traffic_dump is None:
                self._traffic_dump = open('traffic.dump', 'wb')
            self._traffic_dump.write(data)
        if self.fake:
            return
        self._pending_data.write(data)
        if self._pending_data.tell() > self.mtu * 16 and not self._paused:
            self.flush()

    def _print_bitmap(self, data: PrinterData):
        paper_width = self.model.paper_width
        flip(data.data, data.width, data.height, self.flip_h, self.flip_v, overwrite=True)
        if self.model.is_new_kind:
            self.start_printing_new()
        else:
            self.start_printing()
        if self.use_text_mode:
            self.text_mode()
        else:
            self.image_mode()
        # TODO: specify other commands
        self.start_lattice()
        # TODO: consider compression on new devices
        for chunk in data.read(paper_width // 8):
            if self.dry_run:
                chunk = b'\x00' * len(chunk)
            self.draw_bitmap(chunk)
        if self.dump:
            with open('dump.pbm', 'wb') as dump_pbm:
                dump_pbm.write(next(data.to_pbm(merge_pages=True)))
        self.end_lattice()
        # TODO: adjustable
        self.feed_paper(128)
        self.flush()

    def _print_text(self, file: io.BufferedIOBase):
        paper_width = self.model.paper_width
        text_io = io.TextIOWrapper(file, encoding='utf-8')
        if self.text_canvas is None:
            self.text_canvas = TextCanvas(paper_width, wrap=self.wrap,
                rtl=self.rtl, font_path=self.font_family + '.pf2')
        if file is sys.stdin.buffer:
            pf2 = self.text_canvas.pf2
            info(I18n['font-size-0', pf2.point_size])
            width_stats = {}
            for i in range(0x20, 0x7f):
                char = chr(i)
                width_stats[char] = pf2[char].width
            average = pf2.point_size // 2
            if (width_stats[' '] == width_stats['i'] ==
                width_stats['m'] == width_stats['M']):
                average = width_stats['A']
            else:
                average = (width_stats['a'] + width_stats['A'] +
                           width_stats['0'] + width_stats['+']) // 4
            info('-------+' * (paper_width // average // 8) +
                 '-' * (paper_width // average % 8))
        if self.model.is_new_kind:
            self.start_printing_new()
        else:
            self.start_printing()
        if self.use_text_mode:
            self.text_mode()
        else:
            self.image_mode()
        # TODO: specify other commands
        self.start_lattice()
        printer_data = PrinterData(paper_width)
        buffer = io.BytesIO()
        try:
            while line := text_io.readline():
                if '\x00' in line:
                    error('input-is-not-text-file', exception=PrinterError)
                line_count = 0
                for data in self.text_canvas.puttext(line):
                    buffer.write(data)
                    line_count += 1
                flip(buffer, self.text_canvas.width, self.text_canvas.height * line_count,
                     self.flip_h, self.flip_v, overwrite=True)
                while chunk := buffer.read(paper_width // 8):
                    printer_data.write(chunk)
                    if self.dry_run:
                        chunk = b'\x00' * len(chunk)
                    self.draw_bitmap(chunk)
                buffer.seek(0)
                buffer.truncate()
                self.flush()
        except UnicodeDecodeError:
            error('input-is-not-text-file', exception=PrinterError)
        if self.dump:
            with open('dump.pbm', 'wb') as dump_pbm:
                dump_pbm.write(next(printer_data.to_pbm(merge_pages=True)))
        self.end_lattice()
        # TODO: adjustable
        self.feed_paper(128)
        self.flush()

    def unload(self):
        ''' Unload this instance, disconnect device and clean up.
        '''
        if self.device is not None:
            info(I18n['disconnecting-from-printer'])
            try:
                self.loop(
                    self.device.stop_notify(self.rx_characteristic),
                    self.device.disconnect()
                )
            except (BleakError, EOFError):
                self.device = None
        if self._traffic_dump is not None:
            self._traffic_dump.close()
        self._loop.close()

# CLI procedure

def magick_text(stdin, image_width, font_size, font_family):
    'Pipe an io to ImageMagick for processing text to image, return output io'
    read_fd, write_fd = os.pipe()
    subprocess.Popen(['magick', '-background', 'white', '-fill', 'black',
        '-size', f'{image_width}x', '-font', font_family, '-pointsize', str(font_size),
        'caption:@-', 'pbm:-'],
        stdin=stdin, stdout=io.FileIO(write_fd, 'w'))
    return io.FileIO(read_fd, 'r')

def magick_image(stdin, image_width, dither):
    'Pipe an io to ImageMagick for processing "usual" image to pbm, return output io'
    read_fd, write_fd = os.pipe()
    subprocess.Popen(['magick', '-', '-fill', 'white', '-opaque', 'transparent',
        '-resize', f'{image_width}x', '-dither', dither, '-monochrome', 'pbm:-'],
        stdin=stdin, stdout=io.FileIO(write_fd, 'w'))
    return io.FileIO(read_fd, 'r')

class HelpFormatterI18n(argparse.HelpFormatter):
    'How dare the author of this thing hardcode strings and a colon?'

    class _Section(argparse.HelpFormatter._Section):    # pylint: disable=protected-access
        'For removing trailing hardcoded colon. Many cultures have their own'

        def format_help(self):
            lines = super().format_help().split('\n')
            if len(lines) > 1 and lines[1].endswith(':'):
                lines[1] = lines[1][:-1] + '\n'
            return '\n'.join(lines)

    def _format_usage(self, usage, actions, groups, prefix=None):
        return super()._format_usage(usage, actions, groups, I18n['usage-'])

class ArgumentParserI18n(argparse.ArgumentParser):
    'For using our i18n instead of gettext'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, formatter_class=HelpFormatterI18n, add_help=False)
        del self._positionals
        del self._optionals
        add_group = self.add_argument_group
        self._positionals = add_group(I18n['positional-arguments-'])
        self._optionals = add_group(I18n['options-'])

    def add_argument(self, *args, **kwargs):
        if 'required' not in kwargs and len(args) > 1 and args[1].startswith('-'):
            kwargs['required'] = False
        super().add_argument(*args, **kwargs)

Printer = None

def _main():
    'Main routine for direct command line execution'
    parser = ArgumentParserI18n(
        description='  '.join([
            I18n['print-to-cat-printer'],
            I18n['supported-models-'],
            str((*Models, ))
        ])
    )
    # TODO: group some switches to dedicated help
    parser.add_argument('-h', '--help', action='store_true',
                        help=I18n['show-this-help-message'])
    parser.add_argument('file', default='-', metavar='File', type=str,
                        help=I18n['path-to-input-file-dash-for-stdin'])
    parser.add_argument('-s', '--scan', metavar='Time[,XY01[,MacAddress]]', default='3', type=str,
                        help=I18n['scan-for-a-printer'])
    parser.add_argument('-c', '--convert', metavar='text|image', type=str, default='',
                        help=I18n['convert-input-image-with-imagemagick'])
    parser.add_argument('-p', '--image', metavar='flip|fliph|flipv', type=str, default='',
                        help=I18n['image-printing-options'])
    parser.add_argument('-t', '--text', metavar='Size[,FontFamily][,pf2][,nowrap][,rtl]', type=str,
                        default='', help=I18n['text-printing-mode-with-options'])
    parser.add_argument('-d', '--dry', action='store_true',
                        help=I18n['dry-run-test-print-process-only'])
    parser.add_argument('-f', '--fake', metavar='XY01', type=str, default='',
                        help=I18n['virtual-run-on-specified-model'])
    parser.add_argument('-m', '--dump', action='store_true',
                        help=I18n['dump-the-traffic'])
    parser.add_argument('-n', '--nothing', action='store_true',
                        help=I18n['do-nothing'])

    if len(sys.argv) < 2 or '-h' in sys.argv or '--help' in sys.argv:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    printer = PrinterDriver()

    scan_param = args.scan.split(',')
    printer.scan_timeout = float(scan_param[0])
    identifier = ','.join(scan_param[1:])

    image_param = args.image.split(',')
    if 'flip' in image_param:
        printer.flip_h = True
        printer.flip_v = True
    elif 'fliph' in image_param:
        printer.flip_h = True
    elif 'flipv' in image_param:
        printer.flip_v = True

    if args.text:
        text_param = args.text.split(',')
        font_size = int(text_param[0]) if len(text_param) > 0 else None
        font_family = text_param[1] if len(text_param) > 1 else None
        printer.wrap = 'nowrap' not in text_param
        printer.rtl = 'rtl' in text_param

    info(I18n['cat-printer'])

    if args.dry:
        info(I18n['dry-run-test-print-process-only'])
        printer.dry_run = True
    if args.fake:
        printer.fake = True
        printer.model = Models[args.fake]
    else:
        info(I18n['connecting'])
        printer.scan(identifier, use_result=True)
    printer.dump = args.dump

    mode = 'pbm'

    if args.file == '-':
        file = sys.stdin.buffer
    else:
        file = open(args.file, 'rb')

    if args.text:
        info(I18n['text-printing-mode'])
        printer.use_text_mode = True
        printer.font_family = font_family or 'font'
        if 'pf2' not in text_param:
            # TODO: remove hardcoded width
            file = magick_text(file, 384,
                font_size, font_family)
        else:
            mode = 'text'
    elif args.convert:
        file = magick_image(file, 384, (
            'None'
            if args.convert == 'text'
            else 'FloydSteinberg')
        )

    if args.nothing:
        global Printer
        Printer = printer
        return
    try:
        printer.print(file, mode=mode)
        info(I18n['finished'])
    except KeyboardInterrupt:
        info(I18n['stopping'])
    finally:
        file.close()
        printer.unload()

def main():
    'Run the `_main` routine while catching exceptions'
    try:
        _main()
    except BleakError as e:
        error_message = str(e)
        if (
            ('not turned on' in error_message) or   # windows or android
            (isinstance(e, BleakDBusError) and      # linux/dbus/bluetoothctl
             getattr(e, 'dbus_error') == 'org.bluez.Error.NotReady')
        ):
            fatal(I18n['please-enable-bluetooth'], code=ExitCodes.GeneralError)
        else:
            raise
    except PrinterError as e:
        fatal(e.message_localized, code=ExitCodes.PrinterError)
    except RuntimeError as e:
        if 'no running event loop' in str(e):
            pass    # non-sense
        else:
            raise

if __name__ == '__main__':
    main()
