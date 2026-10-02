"""Read only an explicitly supplied AMD64 test dump; never emit memory strings.

Optional developer dependency: pip install minidump==0.0.24.
Raw stack words are candidates, NOT a symbolized/unwound call stack.
"""
import argparse
import json
import logging
import ntpath
import struct

from minidump.minidumpfile import MinidumpFile
from minidump.streams.ContextStream import CONTEXT
from minidump.streams.SystemInfoStream import PROCESSOR_ARCHITECTURE


def inspect(path, image=None):
    dump = MinidumpFile.parse(str(path))
    if dump.sysinfo.ProcessorArchitecture != PROCESSOR_ARCHITECTURE.AMD64:
        raise ValueError("only AMD64 dump context is supported")
    reader = dump.get_reader()
    def module_at(address):
        for module in dump.modules.modules:
            if module.baseaddress <= address < module.baseaddress + module.size:
                return ntpath.basename(module.name) + "+" + hex(address-module.baseaddress)
        return None
    result = []
    for exception in dump.exception.exception_records:
        record = exception.ExceptionRecord
        dump.file_handle.seek(exception.ThreadContext.Rva)
        context = CONTEXT.parse(dump.file_handle)
        words = []
        for offset in range(0, 1024, 8):
            try: address = struct.unpack("<Q",reader.read(context.Rsp+offset,8))[0]
            except Exception: break
            module = module_at(address)
            if module: words.append({"rsp_offset":hex(offset),"module_address":module})
        result.append({"exception":hex(record.ExceptionCode_raw),"parameters":record.ExceptionInformation,
            "thread_id":exception.ThreadId,"fault_module_address":module_at(record.ExceptionAddress),
            "instruction_pointer":module_at(context.Rip),"rdi_module_address":module_at(context.Rdi),
            "raw_stack_candidates_not_unwound":words})
        if image:
            import capstone
            import pefile
            pe = pefile.PE(str(image))
            module = next(m for m in dump.modules.modules if ntpath.basename(m.name).lower()==ntpath.basename(str(image)).lower())
            if pe.FILE_HEADER.TimeDateStamp != module.timestamp or pe.OPTIONAL_HEADER.SizeOfImage != module.size:
                raise ValueError("image timestamp/size does not match dump module")
            disassembler=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
            # Fault plus first two code-like raw stack candidates; not an unwind.
            addresses=[record.ExceptionAddress]+[struct.unpack("<Q",reader.read(context.Rsp+int(word["rsp_offset"],16),8))[0] for word in words[:2]]
            functions=[]
            for address in addresses:
                rva=address-module.baseaddress
                entry=next((e.struct for e in pe.DIRECTORY_ENTRY_EXCEPTION if e.struct.BeginAddress<=rva<e.struct.EndAddress),None)
                if entry is None: continue
                instructions=[{"rva":hex(i.address),"instruction":i.mnemonic+" "+i.op_str}
                    for i in disassembler.disasm(pe.get_data(entry.BeginAddress,min(128,entry.EndAddress-entry.BeginAddress)),entry.BeginAddress)]
                functions.append({"start_rva":hex(entry.BeginAddress),"end_rva":hex(entry.EndAddress),"instructions":instructions})
            result[-1]["matching_image_functions_not_symbolized"]=functions
            pe.close()
    dump.file_handle.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump")
    parser.add_argument("--image",help="Optional matching DLL: requires pefile and capstone, never loads/executes the image")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)  # Missing PEB is irrelevant; do not print environment data.
    print(json.dumps(inspect(args.dump,args.image),indent=2))
