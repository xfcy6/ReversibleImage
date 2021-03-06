import torch
import torch.nn as nn
from noise_layers.crop import get_random_rectangle_inside
import matplotlib.pyplot as plt
import numpy as np
from config import Encoder_Localizer_config
import math

class Cropout(nn.Module):
    """
    Combines the noised and cover images into a single image, as follows: Takes a crop of the noised image, and takes the rest from
    the cover image. The resulting image has the same size as the original and the noised images.
    """
    def __init__(self, shape, config=Encoder_Localizer_config(), device=torch.device("cuda")):
        super(Cropout, self).__init__()
        self.config = config
        self.height_ratio_range, self.width_ratio_range = shape[0], shape[1]
        self.device = device

    def forward(self, noised_image,cover_image):
        # noised_image = noised_and_cover[0]
        # cover_image = noised_and_cover[1]
        assert noised_image.shape == cover_image.shape
        sum_attacked = 0
        cropout_mask = torch.zeros_like(noised_image)
        block_height, block_width = int(noised_image.shape[2] / 16), int(noised_image.shape[3] / 16)
        cropout_label = torch.zeros((noised_image.shape[0], 2, block_height, block_width), requires_grad=False)
        cropout_label[:, 1, :, :] = 1
        # 不断修改小块，直到修改面积至少为全图的50%
        while sum_attacked<self.config.min_required_block_portion:
            h_start, h_end, w_start, w_end, ratio = get_random_rectangle_inside(image=noised_image,
                                                                         height_ratio_range=(8/256,self.height_ratio_range),
                                                                         width_ratio_range=(8/256,self.width_ratio_range))
            sum_attacked += ratio
            # 被修改的区域内赋值1, dims: batch channel height width
            cropout_mask[:, :, h_start:h_end, w_start:w_end] = 1
            cropout_label[:, 0, math.floor(h_start / 16):math.ceil(h_end / 16), math.floor(w_start / 16):math.ceil(w_end / 16)] = 1
            cropout_label[:, 1, math.floor(h_start / 16):math.ceil(h_end / 16), math.floor(w_start / 16):math.ceil(w_end / 16)] = 0



        # 生成label：被修改区域对应的8*8小块赋值为1, height/width
        # 一维
        # cropout_label = torch.zeros((noised_image.shape[0],block_height*block_width), requires_grad=False)
        # for row in range(int(h_start/16),int(h_end/16)):
        #     cropout_label[:, row*block_width+int(w_start/16):row*block_width+int(w_end/16)] = 1

        noised_image = noised_image * cropout_mask + cover_image * (1 - cropout_mask)
        numpy_conducted = cropout_mask.clone().detach().cpu().numpy()
        numpy_groundtruth = cropout_label.data.clone().detach().cpu().numpy()

        #校验：输出图片
        # npimg = noised_image.clone().detach().cpu().numpy()
        # if noised_image.shape[0] == 3:
        #     plt.imshow(np.transpose(npimg, (1, 2, 0)))
        # plt.title('Example ')
        # plt.show()
        return noised_image, cropout_label.to(self.device)

