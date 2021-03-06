# %matplotlib inline
import os

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.optim as optim
import torchvision.transforms as transforms
from torch import utils
from torchvision import datasets, utils
from network.Encoder_Localizer import Encoder_Localizer
from network.Encoder_Decoder import Encoder_Decoder
from config import Encoder_Localizer_config

# Directory path
# os.chdir("..")
if __name__ =='__main__':
    cwd = '.'
    device = torch.device("cuda")
    print(device)
    # Hyper Parameters
    num_epochs = 3
    batch_size = 2
    learning_rate = 0.0001
    beta = 1

    # Mean and std deviation of imagenet dataset. Source: http://cs231n.stanford.edu/reports/2017/pdfs/101.pdf
    std = [0.229, 0.224, 0.225]
    mean = [0.485, 0.456, 0.406]

    # TODO: Define train, validation and models
    MODELS_PATH = './output/models/'
    # TRAIN_PATH = cwd+'/train/'
    # VALID_PATH = cwd+'/valid/'
    VALID_PATH = './sample/valid_coco/'
    TRAIN_PATH = './sample/train_coco/'
    TEST_PATH = './sample/test_coco/'

    if not os.path.exists(MODELS_PATH): os.mkdir(MODELS_PATH)


    def customized_loss(S_prime, C_prime, S, C, B):
        ''' Calculates loss specified on the paper.'''

        loss_cover = torch.nn.functional.mse_loss(C_prime, C)
        loss_secret = torch.nn.functional.mse_loss(S_prime, S)
        loss_all = loss_cover + B * loss_secret
        return loss_all, loss_cover, loss_secret

    def localization_loss(pred_label, cropout_label, train_hidden, train_covers, beta=1):
        ''' 自定义localization_loss '''

        loss_localization = torch.nn.functional.mse_loss(pred_label, cropout_label)
        loss_cover = torch.nn.functional.mse_loss(train_hidden, train_covers)
        loss_all = beta * loss_localization + loss_cover
        return loss_all, loss_localization, loss_cover


    def denormalize(image, std, mean):
        ''' Denormalizes a tensor of images.'''

        for t in range(3):
            image[t, :, :] = (image[t, :, :] * std[t]) + mean[t]
        return image


    def imshow(img, idx, learning_rate, beta):
        '''Prints out an image given in tensor format.'''

        img = denormalize(img, std, mean)
        npimg = img.cpu().numpy()
        plt.imshow(np.transpose(npimg, (1, 2, 0)))
        plt.title('Example ' + str(idx) + ', lr=' + str(learning_rate) + ', B=' + str(beta)+' 隐藏图像 宿主图像 输出图像 提取得到的图像')
        plt.show()
        return


    def train_model(net, train_loader, beta, learning_rate,isSelfRecovery=True):
        # batch:3 epoch:2 data:2*3*224*224

        # Save optimizer
        optimizer = optim.Adam(net.parameters(), lr=learning_rate)

        loss_history = []
        # Iterate over batches performing forward and backward passes
        for epoch in range(num_epochs):

            # Train mode
            net.train()

            train_losses = []
            # Train one epoch
            for idx, train_batch in enumerate(train_loader):
                data, _ = train_batch

                # Saves secret images and secret covers
                if not isSelfRecovery:
                    train_covers = data[:len(data) // 2]
                    train_secrets = data[len(data) // 2:]
                else:
                    # self recovery
                    train_covers = data[:]
                    train_secrets = data[:]

                # Creates variable from secret and cover images
                train_secrets = torch.tensor(train_secrets, requires_grad=False).to(device)
                train_covers = torch.tensor(train_covers, requires_grad=False).to(device)

                # Forward + Backward + Optimize
                optimizer.zero_grad()
                train_hidden, pred_label, cropout_label = net(train_secrets, train_covers)

                # MSE标签距离 loss
                train_loss_all, train_loss_localization, train_loss_cover = \
                    localization_loss(pred_label, cropout_label, train_hidden, train_covers,beta=1000)

                # Calculate loss and perform backprop
                # train_loss, train_loss_cover, train_loss_secret = customized_loss(train_output, train_hidden, train_secrets,
                #                                                                   train_covers, beta)
                train_loss_all.backward()
                optimizer.step()

                # Saves training loss
                train_losses.append(train_loss_all.data.cpu().numpy())
                loss_history.append(train_loss_all.data.cpu().numpy())

                # Prints mini-batch losses
                print('Training: Batch {0}/{1}. Total Loss {2:.4f}, Localization Loss {3:.4f}, Cover Loss {3:.4f} '.format(
                    idx + 1, len(train_loader), train_loss_all.data, train_loss_localization.data, train_loss_cover.data))

            torch.save(net.state_dict(), MODELS_PATH + 'Epoch N{}.pkl'.format(epoch + 1))

            mean_train_loss = np.mean(train_losses)

            # Prints epoch average loss
            print('Epoch [{0}/{1}], Average_loss: {2:.4f}'.format(
                epoch + 1, num_epochs, mean_train_loss))

        return net, mean_train_loss, loss_history


    # Setting
    config = Encoder_Localizer_config()
    isSelfRecovery = True
    skipTraining = False
    # Creates net object
    net = Encoder_Localizer().to(device)
    if not skipTraining:
        # Creates training set
        train_loader = torch.utils.data.DataLoader(
            datasets.ImageFolder(
                TRAIN_PATH,
                transforms.Compose([
                    transforms.Scale(256),
                    transforms.RandomCrop(224),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=mean,
                                         std=std)
                ])), batch_size=batch_size, num_workers=1,
            pin_memory=True, shuffle=True, drop_last=True)

        # Creates test set
        test_loader = torch.utils.data.DataLoader(
            datasets.ImageFolder(
                TEST_PATH,
                transforms.Compose([
                    transforms.Scale(256),
                    transforms.RandomCrop(224),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=mean,
                                         std=std)
                ])), batch_size=1, num_workers=1,
            pin_memory=True, shuffle=True, drop_last=True)

        net, mean_train_loss, loss_history = train_model(net, train_loader, beta, learning_rate, isSelfRecovery)
        # Plot loss through epochs
        plt.plot(loss_history)
        plt.title('Model loss')
        plt.ylabel('Loss')
        plt.xlabel('Batch')
        plt.show()
    else:
        net.load_state_dict(torch.load(MODELS_PATH+'Epoch N3.pkl'))

    # Switch to evaluate mode
    net.eval()

    test_losses = []
    # Show images
    for idx, test_batch in enumerate(test_loader):
        # Saves images
        data, _ = test_batch

        # Saves secret images and secret covers
        if not isSelfRecovery:
            test_secret = data[:len(data) // 2]
            test_cover = data[len(data) // 2:]
        else:
            # Self Recovery
            test_secret = data[:]
            test_cover = data[:]


        # Creates variable from secret and cover images
        test_secret = torch.tensor(test_secret, requires_grad=False).to(device)
        test_cover = torch.tensor(test_cover, requires_grad=False).to(device)

        test_hidden, pred_label, cropout_label = net(test_secret, test_cover)
        # MSE标签距离 loss
        test_loss_all, test_loss_localization, test_loss_cover = \
            localization_loss(pred_label, cropout_label, test_hidden, test_cover, beta=1)

        #     diff_S, diff_C = np.abs(np.array(test_output.data[0]) - np.array(test_secret.data[0])), np.abs(np.array(test_hidden.data[0]) - np.array(test_cover.data[0]))

        #     print (diff_S, diff_C)

        if idx in [1, 2, 3, 4]:
            print('Training: Batch {0}/{1}. Total Loss {2:.4f}, Localization Loss {3:.4f}, Cover Loss {3:.4f} '.format(
                idx + 1, len(train_loader), test_loss_all.data, test_loss_localization.data, test_loss_cover.data))

            # Creates img tensor
            # imgs = [test_secret.data,  test_cover.data, test_hidden.data, test_output.data] # 隐藏图像  宿主图像 输出图像 提取得到的图像
            imgs = [test_secret, test_hidden, pred_label]
            imgs_tsor = torch.cat(imgs, 0)

            # Prints Images
            imshow(utils.make_grid(imgs_tsor), idx + 1, learning_rate=learning_rate, beta=beta)

        test_losses.append(test_loss_all.data.cpu().numpy())

    mean_test_loss = np.mean(test_losses)

    print('Average loss on test set: {:.2f}'.format(mean_test_loss))