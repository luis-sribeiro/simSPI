import mrcfile
import numpy as np
import mdtraj as md
import h5py
import os
import math

from scipy.spatial.distance import pdist
from scipy.stats import special_ortho_group


def mrc2data(mrc_file=None):
    """mrc2data
    """
    if mrc_file is not None:
        with mrcfile.open(mrc_file, 'r', permissive=True) as mrc:
            micrograph = mrc.data
        if micrograph is not None:
            if len(micrograph.shape) == 2:
                micrograph = micrograph[np.newaxis, ...]
        else:
            print('Warning! Data in {} is None...'.format(mrc_file))
        return micrograph


def data_and_dic_2hdf5(data, h5_file, dic=None):
    """data_and_dic_2hdf5
    """
    if dic is None:
        dic = {}
    dic['data'] = data
    with h5py.File(h5_file, 'w') as file:
        recursively_save_dict_contents_to_group(file, '/', dic)


def recursively_save_dict_contents_to_group(h5file, path, dic):
    """recursively_save_dict_contents_to_group
    """
    for k, v in dic.items():
        if isinstance(v, (np.ndarray, np.int64, np.float64, int, float, str, bytes)):
            h5file[path + k] = v
        elif isinstance(v, type(None)):
            h5file[path + k] = str('None')
        elif isinstance(v, dict):
            recursively_save_dict_contents_to_group(h5file, path + k + '/', v)
        else:
            raise ValueError('Cannot save %s type' % type(v))


def define_grid_in_fov(
    sample_dimensions, optics_params, detector_params,
    pdb_file=None, dmax=None, pad=1.
):
    """define_grid_in_fov
    """
    fov_Lx, fov_Ly, boxsize = get_fov(
        sample_dimensions, optics_params, detector_params,
        pdb_file=pdb_file, dmax=dmax, pad=pad
    )

    fov_Nx = np.floor(fov_Lx / boxsize)
    fov_Ny = np.floor(fov_Ly / boxsize)

    x_origin = -fov_Lx / 2. + boxsize / 2.
    x_frontier = x_origin + fov_Nx * boxsize
    y_origin = -fov_Ly / 2. + boxsize / 2.
    y_frontier = y_origin + fov_Ny * boxsize

    x_range = np.arange(x_origin, x_frontier, boxsize)
    y_range = np.arange(y_origin, y_frontier, boxsize)
    n_particles = np.int(fov_Nx * fov_Ny)
    return x_range, y_range, n_particles


def get_fov(sample_dimensions, optics_params, detector_params, pdb_file=None, dmax=None, pad=1.):
    """
	"""
    # retrieve arguments (lenths in nm)
    detector_Nx = detector_params[0]
    detector_Ny = detector_params[1]
    detector_pixel_size = detector_params[2] * 1e3
    magnification = optics_params[0]
    hole_diameter = sample_dimensions[0]
    hole_thickness_center = sample_dimensions[1]
    hole_thickness_edge = sample_dimensions[2]
    # define physical size of field-of-view (in nm)
    detector_Lx = detector_Nx * detector_pixel_size
    detector_Ly = detector_Ny * detector_pixel_size
    fov_Lx = detector_Lx / magnification
    fov_Ly = detector_Ly / magnification
    # define particle boxsize (in nm)
    if dmax is None:
        if pdb_file is not None:
            dmax = get_dmax(pdbfile)
        else:
            dmax = 100
    boxsize = dmax + 2 * pad
    #
    return fov_Lx, fov_Ly, boxsize


def get_dmax(filename=None):
    """ get_dmax
    """
    if filename is not None:
        xyz = get_xyz_from_pdb(filename)
        distance = pdist(xyz[0, ...])
        return np.amax(distance)


def get_xyz_from_pdb(filename=None):
    """ get_xyz_from_pdb
    """
    if filename is not None:
        traj = md.load(filename)
        atom_indices = traj.topology.select('name CA or name P')
        traj_small = traj.atom_slice(atom_indices)
        return traj_small.xyz


def write_crd_file(numpart, xrange=np.arange(-100, 110, 10), yrange=np.arange(-100, 110, 10), crd_file='crd.txt',
                   pre_rotate=None):
    """ write_crd_file
    The table should have 6 columns. The first three columns are x, y, and z coordinates of
    the particle center. The following three columns are Euler angles for rotation around
    the z axis, then around the x axis, and again around the z axis. 
    Coordinates are in nm units, and angles in degrees.
    """
    if os.path.exists(crd_file):
        print(crd_file + " already exists.")
    else:
        rotlist = get_rotlist(numpart, pre_rotate=pre_rotate)
        crd = open(crd_file, "w")
        crd.write('# File created by TEM-simulator, version 1.3.\n')
        crd.write('{numpart}  6\n'.format(numpart=numpart))
        crd.write('#            x             y             z           phi         theta           psi  \n')
        l = 0
        for y in yrange:
            for x in xrange:
                if l == int(numpart):
                    break
                crd_table = {'x': x, 'y': y, 'z': 0, 'phi': rotlist[l][0], 'theta': rotlist[l][1], 'psi': rotlist[l][2]}
                crd.write('{0[x]:14.4f}{0[y]:14.4f}{0[z]:14.4f}{0[phi]:14.4f}{0[theta]:14.4f}{0[psi]:14.4f}\n'.format(
                    crd_table))
                l += 1
        crd.close()


def get_rotlist(numpart, pre_rotate=None):
    """ get_rotlist
	"""
    rotlist = []
    for x in range(0, numpart + 1):
        if pre_rotate is None:
            x = special_ortho_group.rvs(3)
            y = rotationMatrixToEulerAngles(x)
        else:
            angle = 360. * np.random.random_sample() - 180.
            y = np.array([angle, pre_rotate[0], pre_rotate[1]])
        rotlist.append(y)
    return rotlist


def rotationMatrixToEulerAngles(R):
    assert (isRotationMatrix(R))
    sy = math.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
    singular = sy < 1e-6
    if not singular:
        x = math.atan2(R[2, 1], R[2, 2])
        y = math.atan2(-R[2, 0], sy)
        z = math.atan2(R[1, 0], R[0, 0])
    else:
        x = math.atan2(-R[1, 2], R[1, 1])
        y = math.atan2(-R[2, 0], sy)
        z = 0
    x = (x * 180) / np.pi
    y = (y * 180) / np.pi
    z = (z * 180) / np.pi
    return np.array([x, y, z])


def isRotationMatrix(R):
    Rt = np.transpose(R)
    shouldBeIdentity = np.dot(Rt, R)
    I = np.identity(3, dtype=R.dtype)
    n = np.linalg.norm(I - shouldBeIdentity)
    return n < 1e-6
