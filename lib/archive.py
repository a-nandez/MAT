import tarfile
import zipfile

import sys
import shutil
import os
import logging

import parser
import mat

class GenericArchiveStripper(parser.Generic_parser):
    '''
        Represent a generic archive
    '''
    def __init__(self, realname, filename, parser, editor, backup, add2archive):
        super(GenericArchiveStripper, self).__init__(realname,
            filename, parser, editor, backup, add2archive)
        self.compression = ''
        self.folder_list = []
        self.add2archive = add2archive

    def remove_folder(self):
        [shutil.rmtree(folder) for folder in self.folder_list]
        self.folder_list = []

    def remove_all(self):
        self._remove_all('normal')

    def remove_all_ugly(self):
        self._remove_all('ugly')

class ZipStripper(GenericArchiveStripper):
    def is_file_clean(self, file):
        if file.comment is not '':
            return False
        elif file.date_time is not 0:
            return False
        elif file.create_system is not 0:
            return False
        elif file.create_version is not 0:
            return False
        else:
            return True

    def is_clean(self):
        zipin = zipfile.ZipFile(self.filename, 'r')
        if zipin.comment != '':
            return False
        for item in zipin.infolist():
            if not self.is_file_clean(item):
                return False
            zipin.extract(item)
            if os.path.isfile(item.filename):
                try:
                    cfile = mat.create_class_file(item.filename, False,
                        self.add2archive)
                except:
                    logging.error('%s is not supported' % item.filename)
                    #Returning false is the best solution imho
                    return False
                mat.secure_remove(item.filename)
            else:
                self.folder_list.insert(0, item.filename)
        zipin.close()
        self.remove_folder()
        return False

    def get_meta(self):
        zipin = zipfile.ZipFile(self.filename, 'r')
        metadata = {}
        for field in zipin.infolist():
            zipmeta = {}
            zipmeta['comment'] = field.comment
            zipmeta['modified'] = field.date_time
            zipmeta['system'] = field.create_system
            zipmeta['zip_version'] = field.create_version
            metadata[field.filename] = zipmeta
        metadata["%s comment" % self.filename] = zipin.comment
        zipin.close()
        return metadata


    def _remove_all(self, method):
        zipin = zipfile.ZipFile(self.filename, 'r')
        zipout = zipfile.ZipFile(self.filename + parser.POSTFIX, 'w',
            allowZip64=True)
        for item in zipin.infolist():
            zipin.extract(item)
            if os.path.isfile(item.filename):
                try:
                    cfile = mat.create_class_file(item.filename, False,
                        self.add2archive)
                    if method is 'normal':
                        cfile.remove_all()
                    else:
                        cfile.remove_all_ugly()
                    logging.debug('Processing %s from %s' % (item.filename,
                        self.filename))
                    zipout.write(item.filename)
                except:
                    logging.info('%s\' fileformat is not supported' %
                        item.filename)
                    if self.add2archive:
                        zipout.write(item.filename)
                mat.secure_remove(item.filename)
            else:
                self.folder_list.insert(0, item.filename)
        zipout.comment = ''
        logging.info('%s treated' % self.filename)
        self.remove_folder()
        zipin.close()
        zipout.close()


class TarStripper(GenericArchiveStripper):
    def _remove(self, current_file):
        '''
            remove the meta added by tar itself to the file
        '''
        current_file.mtime = 0
        current_file.uid = 0
        current_file.gid = 0
        current_file.uname = ''
        current_file.gname = ''
        return current_file

    def _remove_all(self, method):
        tarin = tarfile.open(self.filename, 'r' + self.compression)
        tarout = tarfile.open(self.filename + parser.POSTFIX,
            'w' + self.compression)
        for current_file in tarin.getmembers():
            tarin.extract(current_file)
            if current_file.type is '0': #is current_file a regular file ?
                #no backup file
                try:
                    cfile = mat.create_class_file(current_file.name, False,
                    self.add2archive)
                    if method is 'normal':
                        cfile.remove_all()
                    else:
                        cfile.remove_all_ugly()
                    tarout.add(current_file.name, filter=self._remove)
                except:
                    logging.info('%s\' format is not supported' %
                        current_file.name)
                    if self.add2archive:
                        tarout.add(current_file.name, filter=self._remove)
                mat.secure_remove(current_file.name)
            else:
                self.folder_list.insert(0, current_file.name)
        tarin.close()
        tarout.close()
        self.remove_folder()

        if self.backup is False:
            mat.secure_remove(self.filename)
            os.rename(self.filename + parser.POSTFIX, self.filename)

    def is_file_clean(self, current_file):
        '''
            Check metadatas added by tar
        '''
        if current_file.mtime is not 0:
            return False
        elif current_file.uid is not 0:
            return False
        elif current_file.gid is not 0:
            return False
        elif current_file.uname is not '':
            return False
        elif current_file.gname is not '':
            return False
        else:
            return True

    def is_clean(self):
        tarin = tarfile.open(self.filename, 'r' + self.compression)
        for current_file in tarin.getmembers():
            if not self.is_file_clean(current_file):
                return False
            tarin.extract(current_file)
            if current_file.type is '0': #is current_file a regular file ?
                #no backup file
                class_file = mat.create_class_file(current_file.name, False,
                    self.add2archive)
                if not class_file.is_clean():#if the extracted file is not clean
                    mat.secure_remove(current_file.name) #remove it
                    self.remove_folder() #remove all the remaining folders
                    return False
                mat.secure_remove(current_file.name)
            else:
                self.folder_list.insert(0, current_file.name)
        tarin.close()
        self.remove_folder()
        return True

    def get_meta(self):
        tarin = tarfile.open(self.filename, 'r' + self.compression)
        metadata = {}
        for current_file in tarin.getmembers():
            if current_file.type is '0':
                if not self.is_file_clean(current_file):#if there is meta
                    current_meta = {}
                    current_meta['mtime'] = current_file.mtime
                    current_meta['uid'] = current_file.uid
                    current_meta['gid'] = current_file.gid
                    current_meta['uname'] = current_file.uname
                    current_meta['gname'] = current_file.gname
                    metadata[current_file.name] = current_meta
        tarin.close()
        return metadata


class GzipStripper(TarStripper):
    def __init__(self, realname, filename, parser, editor, backup, add2archive):
        super(GzipStripper, self).__init__(realname,
            filename, parser, editor, backup, add2archive)
        self.compression = ':gz'


class Bzip2Stripper(TarStripper):
    def __init__(self, realname, filename, parser, editor, backup, add2archive):
        super(Bzip2Stripper, self).__init__(realname,
            filename, parser, editor, backup, add2archive)
        self.compression = ':bz2'
