#!/usr/bin/env python

import json
import os.path
import shlex
import uuid


def freeze(obj):
    if isinstance(obj, dict):
        return freeze(set([freeze(x) for x in obj.iteritems()]))
    if isinstance(obj, list):
        return tuple([freeze(x) for x in obj])
    if isinstance(obj, set):
        return frozenset({freeze(x) for x in obj})
    if isinstance(obj, tuple):
        return tuple([freeze(x) for x in obj])
    return obj


def parsecommand(command, directory=os.curdir):
    command = shlex.split(command)
    words = iter(command)
    next(words)  # remove the initial 'cc' / 'c++'

    options = []
    defines = {}
    includes = []
    system_includes = set()

    for word in words:
        if word == '-o':
            next(words)
            continue
        elif word.startswith('-I'):
            include = word[2:]
            include = os.path.abspath(os.path.relpath(include, directory))
            includes.append(include)
        elif word == '-isystem':
            include = next(words)
            include = os.path.abspath(os.path.relpath(include, directory))
            if include not in includes:
                includes.append(include)
            system_includes.add(include)
        elif word.startswith('-D'):
            key, _, value = word[2:].partition('=')
            if value == '':
                value = True
            defines[key] = value
        elif word == '-c':
            continue
        elif word.startswith('-'):
            options.append(word)

    return {
        'options': options,
        'defines': defines,
        'includes': includes,
        'system_includes': system_includes
    }


class CompilationDatabase(object):
    def __init__(self):
        self.targets = {}

    def read(self, input):
        database = json.load(input)
        for entry in database:
            command = freeze(
                parsecommand(entry['command'], directory=entry['directory']))
            self.targets.setdefault(command, set()).add(entry['file'])

    def write(self, output, directory=None):
        output.write('cmake_minimum_required(VERSION 2.8.8)\n')
        output.write('project(autogenerated)\n\n')

        for (config, files) in self.targets.iteritems():
            config = {k: v for (k, v) in config}
            name = uuid.uuid4()

            output.write('add_library(%s OBJECT\n' % name)
            for file in files:
                output.write('    %s\n' % file)
            output.write(')\n')

            output.write('target_compile_options(%s PRIVATE\n' % name)
            for option in config['options']:
                output.write('    %s\n' % option)
            output.write(')\n')

            output.write('target_compile_definitions(%s PRIVATE\n' % name)
            for (define, value) in config['defines']:
                str = define
                if value is not True:
                    str = str + '=' + value
                output.write('    %s\n' % str)
            output.write(')\n')

            output.write('target_include_directories(%s PRIVATE\n' % name)
            for include in config['includes']:
                if directory is not None:
                    include = os.path.relpath(include, directory)
                output.write('    %s\n' % include)
            output.write(')\n')

            output.write(
                'target_include_directories(%s SYSTEM PRIVATE\n' % name)
            for include in config['system_includes']:
                if directory is not None:
                    include = os.path.relpath(include, directory)
                output.write('    %s\n' % include)
            output.write(')\n\n')


def main():
    database = CompilationDatabase()

    with open('compile_commands.json') as input:
        database.read(input)

    with open('CMakeLists.txt', mode='w') as output:
        database.write(output)


if __name__ == '__main__':
    main()
