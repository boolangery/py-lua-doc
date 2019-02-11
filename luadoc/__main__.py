#!/usr/bin/env python3
import sys
import os
import logging
from optparse import OptionParser, OptionGroup
import luadoc
from luadoc import FilesProcessor, Configuration, DocOptions
from luadoc.printers import to_pretty_str, to_pretty_json


def abort(msg):
    sys.stderr.write(msg + '\n')
    sys.exit()


def main():
    default = DocOptions()

    # parse options:
    parser = OptionParser(usage='usage: %prog [options] file|directory',
                          version='%prog ' + luadoc.__version__)
    cli_group = OptionGroup(parser, "CLI Options")
    cli_group.add_option('-s', '--source',
                         metavar='S', type='string',
                         dest='source',
                         help='source passed in a string')
    cli_group.add_option('--config',
                         metavar='F', type='string',
                         dest='config_file',
                         help='path to config file')
    cli_group.add_option('--config-generate',
                         action='store_true',
                         dest='config_generate',
                         help='generate a default config file',
                         default=False)
    cli_group.add_option('-d', '--debug',
                         action='store_true',
                         dest='debug',
                         help='enable debugging messages',
                         default=False)
    cli_group.add_option('-j', '--jobs',
                         metavar='N', type="int",
                         dest='jobs',
                         help='number of parallel jobs in recursive mode',
                         default=4)
    cli_group.add_option('--pretty',
                         action='store_true',
                         dest='pretty',
                         help='python pretty print style',
                         default=False)
    cli_group.add_option('--type',
                         action="append",
                         type='string',
                         dest='extensions',
                         metavar='EXT',
                         help='file extension to indent (can be repeated) [lua]',
                         default=['lua'])
    cli_group.add_option('-p', '--prefix',
                         metavar='S', type='string',
                         dest='comment_prefix',
                         help='the comment prefix used to recognize luadoc comments',
                         default=default.comment_prefix)
    parser.add_option_group(cli_group)

    (options, args) = parser.parse_args()

    # generate config
    if options.config_generate:
        Configuration().generate_default('./luadoc.json')
        sys.exit()

    # check argument:
    if not options.source and not len(args) > 0:
        abort('Expected a filepath')

    # handle options:
    if options.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:\t%(message)s')
    else:
        logging.basicConfig(level=logging.WARNING, format='%(message)s')

    # create doc options
    doc_options = DocOptions()
    doc_options.comment_prefix = options.comment_prefix

    # build a filename list or use source (-s)
    if options.source:
        model = FilesProcessor(8, doc_options).run_for_source(options.source, "")
    else:
        filenames = []
        if not os.path.isdir(args[0]):
            filenames.append(args[0])
        else:
            for root, subdirs, files in os.walk(args[0]):
                for filename in files:
                    if not options.extensions or filename.endswith(tuple(options.extensions)):
                        filepath = os.path.join(root, filename)
                        filenames.append(filepath)

        # process files
        model = FilesProcessor(options.jobs, doc_options).run(filenames)

    # render
    if options.pretty:
        print(to_pretty_str(model))
    else:
        print(to_pretty_json(model))

if __name__ == '__main__':
    main()
