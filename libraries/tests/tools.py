# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
from entropy.const import const_convert_to_rawstring, const_convert_to_unicode
import entropy.tools as et
from entropy.client.interfaces import Client
from entropy.output import print_generic
import tests._misc as _misc
import tempfile
import subprocess
import shutil
import stat

class ToolsTest(unittest.TestCase):

    def setUp(self):
        self.test_pkg = _misc.get_test_entropy_package()
        self.test_pkg2 = _misc.get_test_entropy_package2()
        self.test_pkg3 = _misc.get_test_entropy_package3()
        self.test_pkgs = [self.test_pkg, self.test_pkg2, self.test_pkg3]

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()


    def test_extract_edb(self):

        client = Client(noclientdb = 2, indexing = False, xcache = False,
            repo_validation = False)
        fd, tmp_path = tempfile.mkstemp()

        for test_pkg in self.test_pkgs:
            out_path = et.extract_edb(test_pkg, tmp_path)
            self.assertNotEqual(out_path, None)
            dbconn = client.open_generic_database(out_path)
            dbconn.validateDatabase()
            dbconn.listAllIdpackages()
            dbconn.closeDB()

        os.close(fd)
        os.remove(tmp_path)


    def test_remove_edb(self):

        tmp_path = tempfile.mkdtemp()

        for test_pkg in self.test_pkgs:
            self.assert_(et.is_entropy_package_file(test_pkg))
            out_path = et.remove_edb(test_pkg, tmp_path)
            self.assertNotEqual(out_path, None)
            self.assert_(os.path.isfile(out_path))
            self.assert_(not et.is_entropy_package_file(out_path))

        shutil.rmtree(tmp_path)


    def test_tb(self):
        # traceback test
        tb = None
        try:
            raise ValueError()
        except ValueError:
            tb = et.get_traceback()
        self.assert_(tb)


    def test_get_remote_data(self):

        fd, tmp_path = tempfile.mkstemp()
        msg = const_convert_to_rawstring("helloàòè\n", 'utf-8')
        os.write(fd, msg)
        os.fsync(fd)

        recv_msg = et.get_remote_data("file://"+tmp_path)
        self.assertEqual([msg], recv_msg)

        os.close(fd)
        os.remove(tmp_path)


    def test_supported_img_file(self):
        fd, tmp_path = tempfile.mkstemp()

        # create gif
        os.write(fd, const_convert_to_rawstring("GIF89xxx"))
        os.fsync(fd)
        self.assert_(et.is_supported_image_file(tmp_path))
        self.assert_(et._is_gif_file(tmp_path))

        os.close(fd)
        os.remove(tmp_path)

        png_file = _misc.get_png()
        self.assert_(et.is_supported_image_file(png_file))
        self.assert_(et._is_png_file(png_file))


    def test_valid_ascii(self):
        valid = "ciao"
        non_valid = "òèàò"
        self.assert_(et.is_valid_ascii(valid))
        self.assert_(not et.is_valid_ascii(non_valid))


    def test_is_valid_unicode(self):
        valid = "ciao"
        valid2 = const_convert_to_unicode("òèàò", 'utf-8')
        self.assert_(et.is_valid_unicode(valid))
        self.assert_(et.is_valid_unicode(valid2))


    def test_is_valid_email(self):
        valid = "entropy@entropy.it"
        non_valid = "entropy.entropy.it"
        self.assert_(et.is_valid_email(valid))
        self.assert_(not et.is_valid_email(non_valid))


    def test_islive(self):
        self.assert_(not et.islive())


    def test_get_file_size(self):
        fd, tmp_path = tempfile.mkstemp()
        os.write(fd, const_convert_to_rawstring("ciao"))
        os.fsync(fd)
        self.assertEqual(et.get_file_size(tmp_path), 4)
        os.close(fd)
        os.remove(tmp_path)


    def test_sum_file_sizes(self):
        fd, tmp_path = tempfile.mkstemp()
        fd2, tmp_path2 = tempfile.mkstemp()
        os.write(fd, const_convert_to_rawstring("ciao"))
        os.write(fd2, const_convert_to_rawstring("ciao"))

        self.assertEqual(et.sum_file_sizes([tmp_path, tmp_path2]), 8)

        os.close(fd)
        os.remove(tmp_path)
        os.close(fd2)
        os.remove(tmp_path2)

    def test_check_required_space(self):
        self.assert_(et.check_required_space("/", 10), True)

    def test_getstatusoutput(self):
        cmd = "echo hello"
        out = et.getstatusoutput(cmd)
        self.assertEqual(out, (0, "hello",))

    def test_movefile(self):

        # move file
        fd, tmp_path = tempfile.mkstemp()
        os.close(fd)

        dest_path = tmp_path + "foo"
        self.assert_(et.movefile(tmp_path, dest_path))
        self.assert_(os.stat(dest_path))

        os.remove(dest_path)

        # move symlink
        fd, tmp_path = tempfile.mkstemp()
        dst_link = tmp_path + "foo2"
        dst_final_link = dst_link + "foo3"
        os.symlink(tmp_path, dst_link)
        self.assert_(et.movefile(dst_link, dst_final_link))
        self.assert_(os.stat(dst_final_link))

        os.close(fd)
        os.remove(dst_final_link)

    def test_get_random_number(self):
        rand1 = et.get_random_number()
        rand2 = et.get_random_number()
        self.assert_(isinstance(rand1, int))
        self.assert_(rand1 != rand2)

    def test_split_indexable_into_chunks(self):

        indexable = "asdXasdXasdXasdXasdXasdXasdXasdXasd"
        result = ['asd', 'Xas', 'dXa', 'sdX', 'asd', 'Xas', 'dXa', 'sdX',
            'asd', 'Xas', 'dXa', 'sd']
        out = et.split_indexable_into_chunks(indexable, 3)
        self.assert_(out)
        self.assert_(out == result)

    def test_shaXXX(self):

        fd, tmp_path = tempfile.mkstemp()

        os.write(fd, const_convert_to_rawstring("this is the life"))
        os.fsync(fd)

        sha1 = et.sha1(tmp_path)
        sha256 = et.sha256(tmp_path)
        sha512 = et.sha512(tmp_path)
        r_sha1 = "105de2055ac81db7b02a27623b7e73932788df95"
        r_sha256 = "ccb134af19d748c9c845b26a1e3a29e6ea356d1f1e0ad47d57b83f38c5492988"
        r_sha512 = "a1e88ef22f5884cd8b205c2e6e2b17ae0f7597df81fabc6a4e77454ac688102df8986353c9f97981b4274f61c6a0ca4c74ec2fd49997b4a35d4091d94dc8a64e"

        self.assertEqual(sha1, r_sha1)
        self.assertEqual(sha256, r_sha256)
        self.assertEqual(sha512, r_sha512)

        os.close(fd)
        os.remove(tmp_path)

    def test_md5sum_directory(self):
        tmp_dir = tempfile.mkdtemp()
        f = open(os.path.join(tmp_dir, "foo"), "w")
        f.write("hello world")
        f.flush()
        f.close()

        r_md5dir = "5eb63bbbe01eeed093cb22bb8f5acdc3"
        md5dir = et.md5sum_directory(tmp_dir)
        self.assertEqual(md5dir, r_md5dir)
        mobj = et.md5obj_directory(tmp_dir)
        self.assertEqual(mobj.hexdigest(), r_md5dir)

        shutil.rmtree(tmp_dir)

    def test_XXcompress_file(self):

        import bz2
        fd, tmp_path = tempfile.mkstemp()
        os.write(fd, const_convert_to_rawstring("this is the life"))
        os.fsync(fd)
        orig_md5 = et.md5sum(tmp_path)

        new_path = tmp_path + ".bz2"
        opener = bz2.BZ2File
        et.compress_file(tmp_path, new_path, opener)

        comp_md5 = "69b9fc26f7cb561a067a10b06d890242"
        md5 = et.md5sum(new_path)
        self.assertEqual(md5, comp_md5)
        os.close(fd)

        et.uncompress_file(new_path, tmp_path, opener)
        self.assertEqual(orig_md5, et.md5sum(tmp_path))

        os.remove(tmp_path)
        os.remove(new_path)

    def test_compress_stuff(self):
        paths = [_misc.get_test_entropy_package4(),
            _misc.get_test_entropy_package3()]

        fd, tmp_path = tempfile.mkstemp()
        et.compress_files(tmp_path, paths)
        orig_md5 = "cc3b3af2235b27adad3c604c0d4632b5"
        md5 = et.md5sum(tmp_path)
        self.assertEqual(orig_md5, md5)

        tmp_dir = tempfile.mkdtemp()
        et.universal_uncompress(tmp_path, tmp_dir)
        self.assert_(os.listdir(tmp_dir))

        os.close(fd)
        os.remove(tmp_path)
        shutil.rmtree(tmp_dir)

    def test_unpack_gzip(self):
        import gzip
        fd, tmp_path = tempfile.mkstemp(suffix = ".gz")

        gz_f = gzip.GzipFile(tmp_path, "wb")
        gz_f.write(const_convert_to_rawstring("ciao ciao ciao"))
        gz_f.close()

        new_path = et.unpack_gzip(tmp_path)
        self.assert_(os.stat(new_path))
        orig_md5 = "b40d18c97e6461678f264c4524f6cc7c"
        self.assertEqual(orig_md5, et.md5sum(new_path))

        os.close(fd)
        os.remove(tmp_path)
        os.remove(new_path)

    def test_unpack_bzip2(self):
        import bz2
        fd, tmp_path = tempfile.mkstemp(suffix = ".bz2")

        gz_f = bz2.BZ2File(tmp_path, "wb")
        gz_f.write(const_convert_to_rawstring("ciao ciao ciao"))
        gz_f.close()

        new_path = et.unpack_bzip2(tmp_path)
        self.assert_(os.stat(new_path))
        orig_md5 = "b40d18c97e6461678f264c4524f6cc7c"
        self.assertEqual(orig_md5, et.md5sum(new_path))

        os.close(fd)
        os.remove(tmp_path)
        os.remove(new_path)

    def test_remove_edb(self):
        fd, tmp_path = tempfile.mkstemp()
        tmp_dir = tempfile.mkdtemp()
        shutil.copy2(_misc.get_test_entropy_package4(), tmp_path)

        new_path = et.remove_edb(tmp_path, tmp_dir)
        orig_md5 = "ab1f147202838c6ee9c6fc3511537279"
        self.assertEqual(orig_md5, et.md5sum(new_path))

        os.close(fd)
        os.remove(tmp_path)
        shutil.rmtree(tmp_dir)

    def test_create_md5_file(self):
        fd, tmp_path = tempfile.mkstemp(
            suffix = const_convert_to_unicode("òèà", 'utf-8'))

        os.write(fd, const_convert_to_rawstring("hello"))
        os.fsync(fd)

        cksum = "5d41402abc4b2a76b9719d911017c592"
        md5_path = et.create_md5_file(tmp_path)
        md5_f = open(md5_path, "rb")
        orig_cont = const_convert_to_rawstring(
            cksum + "  " + \
                os.path.basename(tmp_path) + "\n",
            'utf-8')
        self.assertEqual(orig_cont, md5_f.read())
        self.assert_(et.compare_md5(tmp_path, cksum))

        md5_f.close()
        os.close(fd)
        os.remove(tmp_path)
        os.remove(md5_path)

    def test_create_sha1_file(self):
        fd, tmp_path = tempfile.mkstemp(
            suffix = const_convert_to_unicode("òèà", 'utf-8'))

        os.write(fd, const_convert_to_rawstring("hello"))
        os.fsync(fd)

        cksum = "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"
        sha_path = et.create_sha1_file(tmp_path)
        sha_f = open(sha_path, "rb")
        orig_cont = const_convert_to_rawstring(
            cksum + "  " + \
                os.path.basename(tmp_path) + "\n",
            'utf-8')
        self.assertEqual(orig_cont, sha_f.read())
        self.assert_(et.compare_sha1(tmp_path, cksum))

        sha_f.close()
        os.close(fd)
        os.remove(tmp_path)
        os.remove(sha_path)

    def test_create_sha256_file(self):
        fd, tmp_path = tempfile.mkstemp(
            suffix = const_convert_to_unicode("òèà", 'utf-8'))

        os.write(fd, const_convert_to_rawstring("hello"))
        os.fsync(fd)

        cksum = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        sha_path = et.create_sha256_file(tmp_path)
        sha_f = open(sha_path, "rb")
        orig_cont = const_convert_to_rawstring(
            cksum + "  " + \
                os.path.basename(tmp_path) + "\n",
            'utf-8')
        self.assertEqual(orig_cont, sha_f.read())
        self.assert_(et.compare_sha256(tmp_path, cksum))

        sha_f.close()
        os.close(fd)
        os.remove(tmp_path)
        os.remove(sha_path)

    def test_create_sha512_file(self):
        fd, tmp_path = tempfile.mkstemp(
            suffix = const_convert_to_unicode("òèà", 'utf-8'))

        os.write(fd, const_convert_to_rawstring("hello"))
        os.fsync(fd)

        cksum = "9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca72323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043"
        sha_path = et.create_sha512_file(tmp_path)
        sha_f = open(sha_path, "rb")
        orig_cont = const_convert_to_rawstring(
            cksum+"  " + \
                os.path.basename(tmp_path) + "\n",
            'utf-8')
        self.assertEqual(orig_cont, sha_f.read())
        self.assert_(et.compare_sha512(tmp_path, cksum))

        sha_f.close()
        os.close(fd)
        os.remove(tmp_path)
        os.remove(sha_path)

    def test_allocate_masked_file(self):
        fd, tmp_path = tempfile.mkstemp()
        fd2, tmp_path2 = tempfile.mkstemp()

        os.write(fd, const_convert_to_rawstring("this is new"))
        os.fsync(fd)

        new_path, done = et.allocate_masked_file(tmp_path, tmp_path2)
        self.assert_(done)
        predicted_new = os.path.join(os.path.dirname(tmp_path), "._cfg0000_" + \
            os.path.basename(tmp_path))
        self.assertEqual(predicted_new, new_path)

        os.close(fd)
        os.remove(tmp_path)
        os.close(fd2)
        os.remove(tmp_path2)

    def test_isjustpkgname(self):
        self.assert_(et.isjustpkgname("foo"))
        self.assert_(not et.isjustpkgname("app-misc/foo-1.2.3"))

    def test_isvalidatom(self):
        self.assert_(not et.isvalidatom('media-libs/test-3.0'))
        self.assert_(et.isvalidatom('>=media-libs/test-3.0'))

    def test_md5string(self):
        mystring = "ciao"
        out_str = et.md5string(mystring)
        self.assertEqual(out_str, "6e6bc4e49dd477ebc98ef4046c067b5f")

    def test_get_operator(self):
        ops = {
            '>=': "media-libs/foo",
            '<': "media-libs/foo",
            '<=': "media-libs/foo",
            '~': "media-libs/foo",
        }
        for op, key in ops.items():
            self.assertEqual(op, et.get_operator(op + key))

    def test_isjustname(self):
        self.assert_(not et.isjustname("app-foo/foo-1.2.3"))
        self.assert_(et.isjustname("app-foo/foo"))

    def test_isspecific(self):
        self.assert_(et.isspecific("app-foo/foo-1.2.3"))
        self.assert_(not et.isspecific("app-foo/foo"))

    def test_catpkgsplit(self):
        data = {
            'app-foo/foo-1.2.3': ["app-foo", "foo", "1.2.3", "r0"],
        }
        for atom, split_data in data.items():
            pkgsplit = et.catpkgsplit(atom)
            self.assertEqual(split_data, pkgsplit)

    def test_dep_getkey(self):
        pkg = "app-foo/foo-1.2.3"
        key = "app-foo/foo"
        self.assertEqual(key, et.dep_getkey(pkg))

    def test_dep_getcpv(self):
        pkg = ">=app-foo/foo-1.2.3"
        cpv = "app-foo/foo-1.2.3"
        self.assertEqual(cpv, et.dep_getcpv(pkg))

    def test_dep_getslot(self):
        pkg = ">=app-foo/foo-1.2.3:2.3.4"
        slot = "2.3.4"
        self.assertEqual(slot, et.dep_getslot(pkg))

    def test_dep_getusedeps(self):
        pkg = ">=app-foo/foo-1.2.3:2.3.4[ciao,come,va]"
        usedeps = ("ciao", "come", "va")
        self.assertEqual(usedeps, et.dep_getusedeps(pkg))

    def test_remove_usedeps(self):
        pkg = ">=app-foo/foo-1.2.3:2.3.4[ciao,come,va]"
        result = ">=app-foo/foo-1.2.3:2.3.4"
        self.assertEqual(result, et.remove_usedeps(pkg))

    def test_remove_slot(self):
        pkg = ">=app-foo/foo-1.2.3:2.3.4"
        result = ">=app-foo/foo-1.2.3"
        self.assertEqual(result, et.remove_slot(pkg))

    def test_remove_revision(self):
        pkg = "app-foo/foo-1.2.3-r1"
        result = "app-foo/foo-1.2.3"
        self.assertEqual(result, et.remove_revision(pkg))

    def test_remove_tag(self):
        pkg = "app-foo/foo-1.2.3-r1#2.2.2-foo"
        result = "app-foo/foo-1.2.3-r1"
        self.assertEqual(result, et.remove_tag(pkg))

    def test_remove_entropy_revision(self):
        pkg = "app-foo/foo-1.2.3-r1#2.2.2-foo~1"
        result = "app-foo/foo-1.2.3-r1#2.2.2-foo"
        self.assertEqual(result, et.remove_entropy_revision(pkg))

    def test_dep_get_entropy_revision(self):
        pkg = "app-foo/foo-1.2.3-r1#2.2.2-foo~1"
        result = 1
        self.assertEqual(result, et.dep_get_entropy_revision(pkg))

    def test_dep_get_spm_revision(self):
        pkg = "app-foo/foo-1.2.3-r1"
        result = "r1"
        self.assertEqual(result, et.dep_get_spm_revision(pkg))

    def test_dep_get_match_in_repos(self):
        pkg = "app-foo/foo-1.2.3-r1@foorepo"
        result = ("app-foo/foo-1.2.3-r1", ["foorepo"])
        self.assertEqual(result, et.dep_get_match_in_repos(pkg))

    def test_dep_gettag(self):
        pkg = "app-foo/foo-1.2.3-r1#2.2.2-foo~1"
        result = "2.2.2-foo"
        self.assertEqual(result, et.dep_gettag(pkg))

    def test_remove_package_operators(self):
        pkg = ">=app-foo/foo-1.2.3:2.3.4~1"
        result = "app-foo/foo-1.2.3:2.3.4~1"
        self.assertEqual(result, et.remove_package_operators(pkg))

    def test_compare_versions(self):
        ver_a = ("1.0.0", "1.0.0", 0,)
        ver_b = ("1.0.1", "1.0.0", 0.10000000000000001,)
        ver_c = ("1.0.0", "1.0.1", -0.10000000000000001,)

        self.assertEqual(et.compare_versions(ver_a[0], ver_a[1]), ver_a[2])
        self.assertEqual(et.compare_versions(ver_b[0], ver_b[1]), ver_b[2])
        self.assertEqual(et.compare_versions(ver_c[0], ver_c[1]), ver_c[2])

    def test_get_newer_version(self):
        vers = ["1.0", "3.4", "0.5", "999", "9999", "10.0"]
        out_vers = ['9999', '999', '10.0', '3.4', '1.0', '0.5']
        self.assertEqual(et.get_newer_version(vers), out_vers)

    def test_get_entropy_newer_version(self):
        vers = [("1.0", "2222", 1,), ("3.4", "2222", 0,), ("1.0", "2223", 1,),
            ("1.0", "2223", 3,)]
        out_vers = [('1.0', '2223', 3), ('1.0', '2223', 1),
            ('3.4', '2222', 0), ('1.0', '2222', 1)]
        self.assertEqual(et.get_entropy_newer_version(vers), out_vers)

    def test_istextfile(self):
        fd, tmp_path = tempfile.mkstemp()

        os.write(fd, const_convert_to_rawstring("this is new"))
        os.fsync(fd)
        self.assert_(et.istextfile(tmp_path))
        os.close(fd)
        os.remove(tmp_path)

    def test_filter_duplicated_entries(self):
        begin = ["1.0", "2", "1.0", "3"]
        end = ["1.0", "2", "3"]
        self.assertEqual(et.filter_duplicated_entries(begin), end)

    def test_escape(self):
        begin = "casdasdas\"asdasdasd\" sadasd "
        end = 'casdasdas""asdasdasd""+sadasd+'
        self.assertEqual(et.escape(begin), end)

    def test_extract_ftp_host_from_uri(self):
        begin = "ftp://test:test@192.168.1.1/home/folder"
        end = "192.168.1.1"
        self.assertEqual(et.extract_ftp_host_from_uri(begin), end)

    def test_spliturl(self):
        begin = "http://www.sabayon.org/download"
        end = ['http', 'www.sabayon.org', '/download', '', '']
        self.assertEqual(list(et.spliturl(begin)), end)

    def test_spawn_function(self):
        fd, tmp_path = tempfile.mkstemp()
        def myfunc(fd):
            os.write(fd, const_convert_to_rawstring("this is new"))
            os.fsync(fd)
            return "ok"

        rc = et.spawn_function(myfunc, fd)
        self.assertEqual(rc, "ok")
        os.close(fd)

        f = open(tmp_path, "r")
        self.assertEqual("this is new", f.read())
        f.close()
        os.remove(tmp_path)

    def test_bytes_into_human(self):
        begin = 102400020
        end = '97.7MB'
        self.assertEqual(et.bytes_into_human(begin), end)

    def test_hide_ftp_password(self):
        begin = "ftp://test:test@192.168.1.1/home/folder"
        end = 'ftp://xxxxxxxx:xxxxxxxx@192.168.1.1/home/folder'
        self.assertEqual(et.hide_ftp_password(begin), end)

    def test_extract_ftp_data(self):
        begin = "ftp://test:test@192.168.1.1/home/folder"
        end = ('test', 'test', 21, '/home/folder')
        self.assertEqual(et.extract_ftp_data(begin), end)

    def test_get_random_temp_file(self):
        self.assert_(et.get_random_temp_file())

    def test_convert_unix_time_to_human_time(self):
        unixtime = 1
        self.assertEqual(et.convert_unix_time_to_human_time(unixtime),
            '1970-01-01 01:00:01')

    def test_convert_unix_time_to_datetime(self):
        unixtime = 1
        import datetime
        self.assertEqual(et.convert_unix_time_to_datetime(unixtime),
            datetime.datetime(1970, 1, 1, 1, 0, 1))

    def test_convert_seconds_to_fancy_output(self):
        seconds = 2740
        self.assertEqual(et.convert_seconds_to_fancy_output(seconds),
            '45m:40s')

    def test_is_valid_string(self):
        valid = "ciasdoad"
        non_valid = "òèàòè"
        self.assert_(et.is_valid_string(valid))
        self.assert_(not et.is_valid_string(non_valid))

    def test_is_valid_md5(self):
        valid = "5d41402abc4b2a76b9719d911017c592"
        non_valid = "asdasdasdasdasdasdaszzzzzzza"
        self.assert_(et.is_valid_md5(valid))
        self.assert_(not et.is_valid_md5(non_valid))

    def test_read_elf_class(self):
        elf_obj = _misc.get_dl_so_amd()
        elf_class = 2
        self.assertEqual(et.read_elf_class(elf_obj), elf_class)

    def test_is_elf_file(self):
        self.assert_(et.is_elf_file(_misc.get_dl_so_amd()))

    def test_read_elf_dyn_libs(self):
        elf_obj = _misc.get_dl_so_amd_2()
        known_meta = set(['libcom_err.so.2', 'libkrb5.so.3',
            'libkrb5support.so.0', 'libgssrpc.so.4', 'libk5crypto.so.3',
            'libc.so.6'])
        metadata = et.read_elf_dynamic_libraries(elf_obj)
        self.assertEqual(metadata, known_meta)

    def test_read_elf_linker_paths(self):
        elf_obj = _misc.get_dl_so_amd_2()
        known_meta = ['/usr/lib64', '/usr/lib64']
        metadata = et.read_elf_linker_paths(elf_obj)
        self.assertEqual(metadata, known_meta)

    def test_xml_from_dict_extended(self):
        data = {
            "foo": 1,
            "foo2": None,
            "foo3": set([1, 2, 3]),
            "foo4": [1, 2, 3],
            "foo5": "ciao",
            "foo6": (1, 2, 3),
            "foo6": 1.25,
            "foo7": {"a": const_convert_to_unicode("ciaoèò", 'utf-8'),},
            "foo8": frozenset([1, 2, 3])
        }
        xml_data = et.xml_from_dict_extended(data)
        new_dict = et.dict_from_xml_extended(xml_data)
        self.assertEqual(data, new_dict)

    def test_xml_from_dict(self):
        data = {
            "foo": "abc",
            "foo2": "def",
            "foo3": "asdas asdasd sdasad",
            "foo4": const_convert_to_unicode("òèà", 'utf-8'),
            "foo5": "ciao",
        }
        xml_data = et.xml_from_dict(data)
        new_dict = et.dict_from_xml(xml_data)
        self.assertEqual(data, new_dict)

    def test_create_package_filename(self):
        category = "app-foo"
        name = "foo"
        version = "1.2.3"
        package_tag = "abc"
        result = 'app-foo:foo-1.2.3#abc.tbz2'
        self.assertEqual(et.create_package_filename(category, name, version,
            package_tag), result)

    def test_create_package_atom_string(self):
        category = "app-foo"
        name = "foo"
        version = "1.2.3"
        package_tag = "abc"
        result = 'app-foo/foo-1.2.3#abc'
        self.assertEqual(et.create_package_atom_string(category, name, version,
            package_tag), result)

    def test_uncompress_tar_bz2(self):

        pkgs = [_misc.get_test_entropy_package4(),
            ] #_misc.get_footar_package() disabled for now
        for pkg in pkgs:
            self._do_uncompress_tar_bz2(pkg)

    def _do_uncompress_tar_bz2(self, pkg_path):

        tmp_dir = tempfile.mkdtemp()
        fd, tmp_file = tempfile.mkstemp()

        path_perms = {}

        # try with tar first
        args = ["tar", "xjfp", pkg_path, "-C", tmp_dir]
        proc = subprocess.Popen(args, stdout = fd, stderr = fd)
        rc = proc.wait()
        self.assert_(not rc)
        os.close(fd)

        for currentdir, subdirs, files in os.walk(tmp_dir):
            for xfile in files:
                path = os.path.join(currentdir, xfile)
                fstat = os.lstat(path)
                mode = stat.S_IMODE(fstat.st_mode)
                uid, gid = fstat.st_uid, fstat.st_gid
                path_perms[path] = (mode, uid, gid,)

        self.assert_(path_perms)

        shutil.rmtree(tmp_dir)
        os.makedirs(tmp_dir)

        # now try with our function
        rc = et.uncompress_tar_bz2(pkg_path, tmp_dir)
        self.assert_(not rc)

        new_path_perms = {}

        for currentdir, subdirs, files in os.walk(tmp_dir):
            for xfile in files:
                path = os.path.join(currentdir, xfile)
                fstat = os.lstat(path)
                mode = stat.S_IMODE(fstat.st_mode)
                uid, gid = fstat.st_uid, fstat.st_gid
                mystat = (mode, uid, gid,)
                new_path_perms[path] = (mode, uid, gid,)

        self.assertEqual(path_perms, new_path_perms)
        shutil.rmtree(tmp_dir)

if __name__ == '__main__':
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        from entropy.const import etpUi
        etpUi['debug'] = True
    unittest.main()
