# Author: Sudeep Pillai <spillai@csail.mit.edu>
# License: MIT

import os
import numpy as np
import cv2
from itertools import izip, repeat

from pybot.utils.db_utils import AttrDict
from pybot.utils.dataset_readers import natural_sort, \
    FileReader, DatasetReader, ImageDatasetReader, \
    StereoDatasetReader, VelodyneDatasetReader

from pybot.geometry.rigid_transform import RigidTransform
from pybot.vision.camera_utils import StereoCamera

def kitti_stereo_calib(sequence, scale=1.0): 
    seq = int(sequence)
    print('KITTI Dataset Reader: Sequence ({:}) @ Scale ({:})'.format(sequence, scale))
    if seq >= 0 and seq <= 2: 
        return KITTIDatasetReader.kitti_00_02.scaled(scale)
    elif seq == 3: 
        return KITTIDatasetReader.kitti_03.scaled(scale)
    elif seq >= 4 and seq <= 12: 
        return KITTIDatasetReader.kitti_04_12.scaled(scale)
    else: 
        raise RuntimeError('Error retrieving stereo calibration for KITTI sequence {:}'.format(sequence))

# def kitti_stereo_calib_params(scale=1.0): 
#     f = 718.856*scale
#     cx, cy = 607.192*scale, 185.2157*scale
#     baseline_px = 386.1448 * scale
#     return get_calib_params(f, f, cx, cy, baseline_px=baseline_px)

def kitti_load_poses(fn): 
    X = (np.fromfile(fn, dtype=np.float64, sep=' ')).reshape(-1,12)
    return map(lambda p: RigidTransform.from_Rt(p[:3,:3], p[:3,3]), 
                map(lambda x: x.reshape(3,4), X))

def kitti_poses_to_str(poses): 
    return "\r\n".join(map(lambda x: " ".join(map(str, 
                                                  (x.matrix[:3,:4]).flatten())), poses))

def kitti_poses_to_mat(poses): 
    return np.vstack(map(lambda x: (x.matrix[:3,:4]).flatten(), poses)).astype(np.float64)


class KITTIDatasetReader(object): 
    """
    KITTIDatasetReader: ImageDatasetReader + VelodyneDatasetReader + Calib
    http://www.cvlibs.net/datasets/kitti/setup.php
    """
    kitti_00_02 = StereoCamera.from_calib_params(718.86, 718.86, 607.19, 185.22, 
                                                 baseline_px=386.1448, shape=np.int32([376, 1241]))
    kitti_03 = StereoCamera.from_calib_params(721.5377, 721.5377, 609.5593, 172.854, 
                                                 baseline_px=387.5744, shape=np.int32([376, 1241]))
    kitti_04_12 = StereoCamera.from_calib_params(707.0912, 707.0912, 601.8873, 183.1104, 
                                                    baseline_px=379.8145, shape=np.int32([376, 1241]))
    baseline = 0.5371 # baseline_px / fx
    velo2cam = 0.27 # Velodyne is 27 cm behind cam_0 (x-forward, y-left, z-up)

    def __init__(self, directory='', 
                 sequence='', 
                 left_template='image_0/%06i.png', 
                 right_template='image_1/%06i.png', 
                 velodyne_template='velodyne/%06i.bin',
                 start_idx=0, max_files=50000, scale=1.0): 

        # Set args
        self.sequence = sequence
        self.scale = scale

        # Get calib
        self.calib = kitti_stereo_calib(sequence, scale=scale)

        # Read stereo images
        seq_directory = os.path.join(os.path.expanduser(directory), 'sequences', sequence)
        self.stereo = StereoDatasetReader(directory=seq_directory, 
                                          left_template=os.path.join(seq_directory,left_template), 
                                          right_template=os.path.join(seq_directory,right_template), 
                                          start_idx=start_idx, max_files=max_files, scale=scale)

        # Read poses
        try: 
            pose_fn = os.path.join(os.path.expanduser(directory), 'poses', ''.join([sequence, '.txt']))
            self.poses = FileReader(pose_fn, process_cb=kitti_load_poses)
        except Exception as e:
            self.poses = repeat(None)

        try: 
            # Read velodyne
            self.velodyne = VelodyneDatasetReader(
                template=os.path.join(seq_directory,velodyne_template), 
                start_idx=start_idx, max_files=max_files
            )
        except Exception as e: 
            self.velodyne = repeat(None)

        print 'Initialized stereo dataset reader with %f scale' % scale

    def iteritems(self, *args, **kwargs): 
        return self.stereo.left.iteritems(*args, **kwargs)

    def iter_stereo_frames(self, *args, **kwargs): 
        return self.stereo.iteritems(*args, **kwargs)

    def iter_velodyne_frames(self, *args, **kwargs):         
        """
        for pc in dataset.iter_velodyne_frames(): 
          X = pc[:,:3]
        """
        return self.velodyne.iteritems(*args, **kwargs)

    def iter_stereo_velodyne_frames(self, *args, **kwargs):         
        return izip(self.left.iteritems(*args, **kwargs), 
                    self.right.iteritems(*args, **kwargs), 
                    self.velodyne.iteritems(*args, **kwargs))

    def iterframes(self, *args, **kwargs): 
        for (left, right), pose in izip(self.iter_stereo_frames(*args, **kwargs), self.poses.iteritems(*args, **kwargs)): 
            yield AttrDict(left=left, right=right, velodyne=None, pose=pose)

    def iter_gt_frames(self, *args, **kwargs): 
        for (left, right), pose in izip(self.iter_stereo_frames(*args, **kwargs), self.poses.iteritems(*args, **kwargs)): 
            yield AttrDict(left=left, right=right, velodyne=None, pose=pose)

    @property
    def stereo_frames(self): 
        return self.iter_stereo_frames()

    @property
    def velodyne_frames(self): 
        return self.iter_velodyne_frames()

    
    # @classmethod
    # def stereo_test_dataset(cls, directory, subdir, scale=1.0):
    #     """
    #     Ground truth dataset iterator
    #     """

    #     left_directory = os.path.join(os.path.expanduser(directory), '%s_0' % subdir)
    #     right_directory = os.path.join(os.path.expanduser(directory), '%s_1' % subdir)
    #     noc_directory = os.path.join(os.path.expanduser(directory), 'disp_noc')
    #     occ_directory = os.path.join(os.path.expanduser(directory), 'disp_occ')

    #     c = cls(sequence='00')
    #     c.scale = scale
    #     c.calib = kitti_stereo_calib(1, scale=scale)

    #     # Stereo is only evaluated on the _10.png images
    #     c.stereo = StereoDatasetReader.from_directory(left_directory, right_directory, pattern='*_10.png')
    #     c.noc = ImageDatasetReader.from_directory(noc_directory)
    #     c.occ = ImageDatasetReader.from_directory(occ_directory)
    #     c.poses = [None] * c.stereo.length

    #     return c

    @classmethod
    def iterscenes(cls, sequences, directory='', 
                   left_template='image_0/%06i.png', right_template='image_1/%06i.png', 
                   velodyne_template='velodyne/%06i.bin', start_idx=0, max_files=50000, 
                   scale=1.0, verbose=False): 
        
        for seq in progressbar(sequences, size=len(sequences), verbose=verbose): 
            yield seq, cls(
                directory=directory, sequence=seq, left_template=left_template, 
                right_template=right_template, velodyne_template=velodyne_template, 
                start_idx=start_idx, max_files=max_files)
            
class KITTIStereoGroundTruthDatasetReader(object): 
    def __init__(self, directory, is_2015=False, scale=1.0):
        """
        Ground truth dataset iterator
        """
        if is_2015: 
            left_dir, right_dir = 'image_2', 'image_3'
            noc_dir, occ_dir = 'disp_noc_0', 'disp_occ_0'
            calib_left, calib_right = 'P2', 'P3'
        else: 
            left_dir, right_dir = 'image_0', 'image_1'
            noc_dir, occ_dir = 'disp_noc', 'disp_occ'
            calib_left, calib_right = 'P0', 'P1'

        self.scale = scale

        # Stereo is only evaluated on the _10.png images
        self.stereo = StereoDatasetReader(os.path.expanduser(directory), 
                                          left_template=''.join([left_dir, '/%06i_10.png']), 
                                          right_template=''.join([right_dir, '/%06i_10.png']), scale=scale, grayscale=True)
        self.noc = ImageDatasetReader(template=os.path.join(os.path.expanduser(directory), noc_dir, '%06i_10.png'))
        self.occ = ImageDatasetReader(template=os.path.join(os.path.expanduser(directory), occ_dir, '%06i_10.png'))

        def calib_read(fn, scale): 
            db = AttrDict.load_yaml(fn)
            P0 = np.float32(db[calib_left].split(' '))
            P1 = np.float32(db[calib_right].split(' '))
            fx, cx, cy = P0[0], P0[2], P0[6]
            baseline_px = np.fabs(P1[3])
            return StereoCamera.from_calib_params(fx, fx, cx, cy, baseline_px=baseline_px)

        self.calib = DatasetReader(template=os.path.join(os.path.expanduser(directory), 'calib/%06i.txt'), 
                                   process_cb=lambda fn: calib_read(fn, scale))

        self.poses = repeat(None)

    def iter_gt_frames(self, *args, **kwargs):
        """
        Iterate over all the ground-truth data
           - For noc, occ disparity conversion, see devkit_stereo_flow/matlab/disp_read.m
        """
        for (left, right), noc, occ, calib in izip(self.iter_stereo_frames(*args, **kwargs), 
                                                         self.noc.iteritems(*args, **kwargs), 
                                                         self.occ.iteritems(*args, **kwargs), 
                                                         self.calib.iteritems(*args, **kwargs)):
            yield AttrDict(left=left, right=right, 
                           depth=(occ/256).astype(np.float32),
                           noc=(noc/256).astype(np.float32), 
                           occ=(occ/256).astype(np.float32), 
                           calib=calib, pose=None)
                
    def iteritems(self, *args, **kwargs): 
        return self.stereo.left.iteritems(*args, **kwargs)

    def iter_stereo_frames(self, *args, **kwargs): 
        return self.stereo.iteritems(*args, **kwargs)

    def iterframes(self, *args, **kwargs): 
        for (left, right), pose in izip(self.iter_stereo_frames(*args, **kwargs), self.poses.iteritems(*args, **kwargs)): 
            yield AttrDict(left=left, right=right, velodyne=None, pose=pose)

    @property
    def stereo_frames(self): 
        return self.iter_stereo_frames()

class KITTIRawDatasetReader(KITTIDatasetReader): 
    """
    KITTIRawDatasetReader: KITTIDatasetReader + OXTS reader
    """

    def __init__(self, directory, 
                 sequence='',
                 left_template='image_00/data/%010i.png', 
                 right_template='image_01/data/%010i.png', 
                 velodyne_template='velodyne_points/data/%010i.bin', 
                 oxt_template='oxts/data/%010i.txt',
                 start_idx=0, max_files=50000, scale=1.0): 
        super(KITTIRawDatasetReader, self).__init__(directory, sequence, 
                                                    left_template=left_template, right_template=right_template, 
                                                    velodyne_template=velodyne_template, 
                                                    start_idx=start_idx, max_files=max_files, scale=scale)

        # Read stereo images
        self.stereo = StereoDatasetReader(directory=directory, 
                                          left_template=left_template, 
                                          right_template=right_template, 
                                          start_idx=start_idx, max_files=max_files, scale=scale)

        # Read poses
        try: 
            pose_fn = os.path.join(os.path.expanduser(directory), 'poses', ''.join([sequence, '.txt']))
            self.poses = FileReader(pose_fn, process_cb=kitti_load_poses)
        except: 
            self.poses = repeat(None)
            
        # Read velodyne
        self.velodyne = VelodyneDatasetReader(
            template=os.path.join(directory,velodyne_template), 
            start_idx=start_idx, max_files=max_files
        )

        # Read oxts
        def kitti_load_oxts(fn): 
            return (np.fromfile(fn, dtype=np.float64, sep=' '))
            
        try: 
            oxt_format_fn = os.path.join(os.path.expanduser(directory), 'oxts/dataformat.txt')
            self.oxt_formats = [line.split(':')[0] for line in open(oxt_format_fn)]
            
            oxt_fn = os.path.join(os.path.expanduser(directory), oxt_template)
            self.oxts = DatasetReader(template=oxt_fn, process_cb=lambda fn: kitti_load_oxts(fn), 
                                      start_idx=start_idx, max_files=max_files)
        except Exception as e:
            self.oxts = repeat(None)
        
    def iterframes(self, *args, **kwargs): 
        for (left, right), pose, oxt in izip(self.iter_stereo_frames(*args, **kwargs), 
                                             self.poses.iteritems(*args, **kwargs), 
                                             self.oxts.iteritems(*args, **kwargs)): 
            yield AttrDict(left=left, right=right, velodyne=None, pose=pose, oxt=AttrDict(zip(self.oxt_formats, oxt)))
    
    @property
    def oxt_fieldnames(self): 
        return self.oxt_formats

    def iter_oxts(self, *args, **kwargs): 
        return self.oxts.iteritems()

class OmnicamDatasetReader(object): 
    """
    OmnicamDatasetReader: ImageDatasetReader + VelodyneDatasetReader + Calib
    """

    def __init__(self, directory='', 
                 sequence='2013_05_14_drive_0008_sync', 
                 left_template='image_02/data/%010i.png', 
                 right_template='image_03/data/%010i.png', 
                 velodyne_template='velodyne_points/data/%010i.bin',
                 start_idx=0, max_files=50000, scale=1.0): 

        # Set args
        self.sequence = sequence
        self.scale = scale

        # Get calib
        # self.calib = kitti_stereo_calib_params(scale=scale)

        # # Read poses
        # try: 
        #     pose_fn = os.path.join(os.path.expanduser(directory), 'poses', ''.join([sequence, '.txt']))
        #     self.poses = kitti_load_poses(fn=pose_fn)
        # except: 
        #     pass

        # Read stereo images
        seq_directory = os.path.join(os.path.expanduser(directory), sequence)
        
        self.stereo = StereoDatasetReader(directory=seq_directory,
                                          left_template=os.path.join(seq_directory,left_template), 
                                          right_template=os.path.join(seq_directory,right_template), 
                                          start_idx=start_idx, max_files=max_files, scale=scale)

        # Read velodyne
        self.velodyne = VelodyneDatasetReader(
            template=os.path.join(seq_directory,velodyne_template), 
            start_idx=start_idx, max_files=max_files
        )

        print 'Initialized stereo dataset reader with %f scale' % scale

    def iter_stereo_frames(self, *args, **kwargs): 
        return self.stereo.iteritems(*args, **kwargs)

    def iter_velodyne_frames(self, *args, **kwargs):         
        return self.velodyne.iteritems(*args, **kwargs)

    def iter_stereo_velodyne_frames(self, *args, **kwargs):         
        return izip(self.left.iteritems(*args, **kwargs), 
                    self.right.iteritems(*args, **kwargs), 
                    self.velodyne.iteritems(*args, **kwargs))

    @property
    def stereo_frames(self): 
        return self.iter_stereo_frames()

    @property
    def velodyne_frames(self): 
        return self.iter_velodyne_frames()

# def test_omnicam(dire):
#     return OmnicamDatasetReader(directory='/media/spillai/MRG-HD1/data/omnidirectional/')


