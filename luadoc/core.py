import os
import sys
import time
import json
import concurrent.futures
import logging
from luadoc.parser import DocParser, DocOptions


class Configuration:
    @staticmethod
    def load(file_path: str):
        with open(file_path) as json_data_file:
            data = json.load(json_data_file)
        options = DocOptions()
        options.__dict__ = data
        return options

    @staticmethod
    def generate_default(file_path: str):
        with open(file_path, 'w') as json_data_file:
            json_data_file.write(
                json.dumps(DocOptions().__dict__,
                           sort_keys=True,
                           indent=4,
                           separators=(',', ': ')))
        print('Config. file generated in: ' + os.path.abspath(file_path))


class FilesProcessor:
    def __init__(self, jobs, doc_options: DocOptions):
        self._jobs = jobs
        self._doc_options: DocOptions = doc_options

    def _process_one(self, file_path):
        """Process one file.
        """
        with open(file_path, encoding=self._doc_options.encoding) as file:
            file_content = file.read()

        doc_parser = DocParser(self._doc_options)

        return doc_parser.build_module_doc_model(file_content, file_path)

    def run(self, files):
        logging.info(str(len(files)) + ' file(s) to process')

        processed = 0
        logging.info('[' + str(processed) + '/' + str(len(files)) + '] file(s) processed')

        # some stats
        start = time.time()
        total_file = 0
        model = []

        # We can use a with statement to ensure threads are cleaned up promptly
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._jobs) as executor:
            # Start process operations and mark each future with its filename
            future_to_file = {executor.submit(self._process_one, file): file for file in files}
            for future in concurrent.futures.as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    total_file += 1
                    model.append(future.result())
                except Exception as exc:
                    logging.error('%r generated an exception: %s' % (file, exc))
                else:
                    processed += 1
                    logging.info('[' + str(processed) + '/' + str(len(files)) + '] file(s) processed, last is ' + file)
                    sys.stdout.flush()

        end = time.time()
        logging.info(str(total_file) + ' files processed in ' + str(round(end - start, 2)) + ' s')
        return model

    def run_for_source(self, source):
        doc_parser = DocParser(self._doc_options)

        model = doc_parser.build_module_doc_model(source)

        return model
