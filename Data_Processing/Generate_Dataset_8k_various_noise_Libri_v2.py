import librosa
import numpy as np
import os
from ourLTFATStft import LTFATStft
import ltfatpy
import imageio
import math
import copy
import numpy as np
fft_hop_size = 64
fft_window_length = 256
clipBelow = -10
anStftWrapper = LTFATStft()
sampling_org = 16000
sampling_fre = 8000
imagesize = 64
trunk_step = 26
#if_ADC_Sampling = True


bit_num = 16
count = 0
phase = "train"
status = "noise"
if status == "noise":
    if_noise = True
    dataset_type_A = "A"
    dataset_type_B = "B"
else:
    if_noise = False
    dataset_type_A = "A"
    dataset_type_B = "B"
n_mels= 64
data_root1 = "../../LibriSpeech_dataset/"
if phase == "test":
    data_root2 = "LibriSpeech/test-clean/"
else:
    data_root2 = "LibriSpeech/train-clean-100/"

data_root = data_root1 + data_root2
print(data_root)
#target_SNR = 50
outroot_A = "../dataset_various_noise_mel/{}_{}".format(phase,dataset_type_A)
outroot_B = "../dataset_various_noise_mel/{}_{}".format(phase,dataset_type_B)
audio_8k_root = "../LibriSpeech_{}k".format(sampling_fre//1000)
print(audio_8k_root)
audio_noise_root = "../LibriSpeech_{}k_various_noise".format(sampling_fre//1000)
#outroot = "./timit_mel_{}_{}k_{}_{}bit_various_noise_{}db".format(status,sampling_fre//1000,phase,bit_num,target_SNR)
test_noise_filenames={0:"babble",1:"destroyerengine",2:"f16",3:"factory",4:"leopard", 5:"m109", 6:"machinegun",7:"pink", 8:"volvo",9:"white"}
train_noise_filenames={0:"babble",1:"destroyerengine",2:"f16",3:"factory",4:"leopard", 5:"m109", 6:"machinegun"}
noise_file_paths = "./NoiseFiles/{}_8000.wav"
mel_matrix = librosa.filters.mel(sr=sampling_fre,n_fft=fft_window_length,n_mels=n_mels)
if not os.path.exists(outroot_A):
    os.makedirs(outroot_A)
if not os.path.exists(outroot_B):
    os.makedirs(outroot_B)
for root,dirs,files in os.walk(data_root):
    #print(root)
    #print(files)
    for name in files:
        if os.path.splitext(name)[1]==".flac":
            audio,sr = librosa.core.load(os.path.join(root,name),sr=sampling_fre,mono=False)
            origin_audio = copy.deepcopy(audio)
            if (len(audio)<=0):
                continue
            # GENERATE 8K AUDIO
            audio_8k_dir = os.path.join(audio_8k_root,root[len(data_root1):])
            #audio_8k_dir = audio_8k_root + root[len(data_root1):]
            print(root + name)
            #print(name)
            if not os.path.exists(audio_8k_dir):
                os.makedirs(audio_8k_dir)
            librosa.output.write_wav(os.path.join(audio_8k_root,root[len(data_root1):],name+".wav"),y=audio,sr=sampling_fre,norm=False)

            count +=1
            audio = audio-np.mean(audio)
            origin_audio = origin_audio - np.mean(origin_audio)
            if phase == "train":
                noise_filenames = train_noise_filenames
            elif phase == "test":
                noise_filenames = test_noise_filenames
            if if_noise == True:
                noise_type = np.random.randint(0,len(noise_filenames))
                noise_filepath = noise_file_paths.format(noise_filenames[noise_type])
                target_SNR = np.random.randint(0, 30)
                noise,sr = librosa.core.load(noise_filepath,sr=sampling_fre,mono=False)
                random_slice= np.random.randint(0,len(noise)-len(audio))
                noise_slice = noise[random_slice:random_slice+len(audio)]
                audio_rms = np.sqrt(np.mean(audio**2))
                noise_rms = np.sqrt(np.mean(noise_slice**2))
                noise_gan = audio_rms/(10**(target_SNR/20)*noise_rms)
                #audio_gan = 10**(target_SNR/20)*noise_rms/audio_rms
                #audio = audio_gan*audio + noise_slice
                audio = audio + noise_gan*noise_slice
                #audio = ADC_Sampling(audio,100)
                name_ext = name + '_{}db_{}'.format(target_SNR, noise_filenames[noise_type])
                #name_ext = name + '_{}db'.format(target_SNR)
                
                audio_noise_dir = os.path.join(audio_noise_root,root[len(data_root1):])
                print(audio_noise_dir)
                if not os.path.exists(audio_noise_dir):
                    os.makedirs(audio_noise_dir)
                librosa.output.write_wav(os.path.join(audio_noise_root,root[len(data_root1):],name_ext+".wav"),y=audio,sr=sampling_fre,norm=False)
                
            audio = audio/np.max(np.abs(audio.flatten()))
            origin_audio = origin_audio/np.max(np.abs(origin_audio.flatten()))
            audio = audio.astype(np.float64)
            origin_audio = origin_audio.astype(np.float64)
            real_DGT = anStftWrapper.oneSidedStft(signal=audio,windowLength=fft_window_length,hopSize=fft_hop_size)
            origin_DGT = anStftWrapper.oneSidedStft(signal=origin_audio,windowLength=fft_window_length,hopSize=fft_hop_size)
            mag = np.abs(real_DGT)
            mag = np.dot(mel_matrix,mag)
            mag = mag/np.max(mag.flatten())
            mag = np.log(np.clip(mag,a_min=np.exp(clipBelow),a_max=None))
            mag = mag/(-1*clipBelow)+1
            origin_mag = np.dot(mel_matrix,np.abs(origin_DGT))
            origin_mag = origin_mag/np.max(origin_mag.flatten())
            origin_mag = np.log(np.clip(origin_mag,a_min=np.exp(clipBelow),a_max=None))/(-1*clipBelow)+1
            assert len(mag) == len(origin_mag)
            if phase == "train":
                for i in range(math.ceil(mag.shape[1]/imagesize)):
                    if (i+1)*imagesize<= mag.shape[1]:
                        slice_mag = mag[:,i*imagesize:(i+1)*imagesize]
                        origin_slice_mag =origin_mag[:,i*imagesize:(i+1)*imagesize]
                    else:
                        slice_mag = mag[:,i*imagesize:]
                        slice_mag = np.pad(slice_mag,(0,imagesize-slice_mag.shape[1]),'constant')
                        origin_slice_mag = origin_mag[:,i*imagesize:]
                        origin_slice_mag = np.pad(origin_slice_mag,(0,imagesize-origin_slice_mag.shape[1]),'constant')
                    slice_mag_ = np.round(slice_mag[0:n_mels,:]*(2**(bit_num)-1))
                    origin_slice_mag_ = np.round(origin_slice_mag[0:n_mels,:]*(2**(bit_num)-1))
                    root_ = root[16:].replace("/","_")
                    filename_A = os.path.join(outroot_A,root_+"_"+name+str(i)+".png")
                    filename_B = os.path.join(outroot_B,root_+"_"+name+str(i)+".png")
                    if bit_num == 16:
                        imageio.imwrite(filename_A,slice_mag_.astype(np.uint16))
                        imageio.imwrite(filename_B,origin_slice_mag_.astype(np.uint16))
                    elif bit_num == 8:
                        imageio.imwrite(filename_A,slice_mag_.astype(np.uint8))
                        imageio.imwrite(filename_B, origin_slice_mag_.astype(np.uint8))
                    else:
                        raise NotImplementedError
            elif phase == "test":
                for i in range(math.ceil(mag.shape[1]/imagesize)):
                    if (i+1)*imagesize<= mag.shape[1]:
                        slice_mag = mag[:,i*imagesize:(i+1)*imagesize]
                        origin_slice_mag =origin_mag[:,i*imagesize:(i+1)*imagesize]
                    else:
                        slice_mag = mag[:,i*imagesize:]
                        slice_mag = np.pad(slice_mag,(0,imagesize-slice_mag.shape[1]),'constant')
                        origin_slice_mag = origin_mag[:,i*imagesize:]
                        origin_slice_mag = np.pad(origin_slice_mag,(0,imagesize-origin_slice_mag.shape[1]),'constant')
                    slice_mag_ = np.round(slice_mag[0:n_mels,:]*(2**(bit_num)-1))
                    origin_slice_mag_ = np.round(origin_slice_mag[0:n_mels,:]*(2**(bit_num)-1))
                    root_ = root[16:].replace("/","_")
                    filename_A = os.path.join(outroot_A,root_+"_"+name+str(i)+".png")
                    filename_B = os.path.join(outroot_B,root_+"_"+name+str(i)+".png")
                    if bit_num == 16:
                        imageio.imwrite(filename_A,slice_mag_.astype(np.uint16))
                        imageio.imwrite(filename_B,origin_slice_mag_.astype(np.uint16))
                    elif bit_num == 8:
                        imageio.imwrite(filename_A,slice_mag_.astype(np.uint8))
                        imageio.imwrite(filename_B, origin_slice_mag_.astype(np.uint8))
                    else:
                        raise NotImplementedError
