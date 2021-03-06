
# coding: utf-8

# In[6]:


import tarfile
import pandas as pd
import numpy as np
import os
import nibabel as nib
import tensorflow as tf
from tensorflow.python.framework import ops
import matplotlib.pyplot as plt
import math


np.random.seed(1)


# In[7]:


data_info = pd.read_csv('data_info.csv')


# In[8]:


data_info['Normal'] = data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"].apply(
    lambda x: 1 if x == 0 else 0)
data_info['NormalToMCI'] = data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"].apply(
    lambda x: 1 if x == 1 else 0)
data_info['MCI'] = data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"].apply(
    lambda x: 1 if x == 2 else 0)
data_info['AD'] = data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"].apply(
    lambda x: 1 if x == 3 else 0)
data_info['OtherDementia'] = data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"].apply(
    lambda x: 1 if x == 4 else 0)


# In[9]:


data_info.head()


# ### 1. Load data

# In[10]:


number_files_loaded = 5
num = int(number_files_loaded/3)
sample_list0 = data_info[data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"]==0].iloc[:num, :]["filename"]
sample_list1 = data_info[data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"]==1].iloc[:num, :]["filename"]
sample_list2 = data_info[data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"]==2].iloc[:num, :]["filename"]
sample_list3 = data_info[data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"]==3].iloc[:num, :]["filename"]
sample_list4 = data_info[data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"]==4].iloc[:num, :]["filename"]
sample_list = pd.concat([sample_list0,sample_list1,sample_list2,sample_list3,sample_list4])
sample_list = pd.concat([sample_list0,sample_list2,sample_list3])

tar = tarfile.open("fs_t1_nacc.tar")
for file in sample_list:
    path = "fs_t1/" + file
    tar.extract(path)
    
sample_data_list = list()
for filename in sample_list:
    # or is it better to use get_fdata()?
    a = nib.load("fs_t1/"+filename).get_data()
    sample_data_list.append(a)
sample_dataset = np.array(sample_data_list, dtype=np.float32)
batch_size, height, width, depth = sample_dataset.shape
channels = 1  # gray-scale instead of RGB
s = sample_dataset.reshape(number_files_loaded, 256, 256, 256, 1)

# In[11]:


y0 = data_info[data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"]==0].iloc[:num, 4:9]
y1 = data_info[data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"]==1].iloc[:num, 4:9]
y2 = data_info[data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"]==2].iloc[:num, 4:9]
y3 = data_info[data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"]==3].iloc[:num, 4:9]
y4 = data_info[data_info["diagnosis_0normal_1normaltomci_2mci_3ad_4otherdementia"]==4].iloc[:num, 4:9]
y = pd.concat([y0,y1,y2,y3,y4])
y = pd.concat([y0,y2,y3])
y = np.array(y)
y[:5]


# ### 2. Split the dataset to training and test sets

# In[12]:


def split_train_test(data, test_ratio):
    """
    Generate shuffled indices to split the original dataset.

    Arguments: -- data: dataset to be handled, with shape (n, n_D0, n_H0, n_W0, n_C0) if input is X, (n, n_y) if input is Y
               -- test_ratio: percentage of the test set in the total dataset

    Returns: -- train_indices: a numpy array of the indices to be chosen for the training set 
                               with size len(data)-int(len(data)*test_ratio)
             -- test_indices: a numpy array of the indices to be chosen for the test set
                              with size int(len(data)*test_ratio)
    """
    shuffled_indices = np.random.permutation(len(data))
    test_set_size = int(len(data)*test_ratio)
    test_indices = shuffled_indices[:test_set_size]
    train_indices = shuffled_indices[test_set_size:]

    return train_indices, test_indices


# In[13]:


train_indices, test_indices = split_train_test(s, 0.2)
X_train_orig = s[train_indices]
X_test_orig = s[test_indices]
Y_train = y[train_indices]
Y_test = y[test_indices]

X_train = X_train_orig/255.
X_test = X_test_orig/255.

print("number of training examples = " + str(X_train.shape[0]))
print("number of test examples = " + str(X_test.shape[0]))
print("X_train shape: " + str(X_train.shape))
print("Y_train shape: " + str(Y_train.shape))
print("X_test shape: " + str(X_test.shape))
print("Y_test shape: " + str(Y_test.shape))


# ### 3. Build the 3D Convolutional Neural Networks model

# - **Create placeholders for input X and Y**

# In[14]:


def create_placeholders(n_D0, n_H0, n_W0, n_C0, n_y):
    """
    Creates the placeholders for the tensorflow session.

    Arguments:
    n_D0 -- scalar, depth of an input image
    n_H0 -- scalar, height of an input image
    n_W0 -- scalar, width of an input image
    n_C0 -- scalar, number of channels of the input
    n_y -- scalar, number of classes

    Returns:
    X -- placeholder for the data input, of shape [None, n_D0, n_H0, n_W0, n_C0] and dtype "float"
    Y -- placeholder for the input labels, of shape [None, n_y] and dtype "float"
    """

    X = tf.placeholder(shape=(None, n_D0, n_H0, n_W0, n_C0), dtype=tf.float32)
    Y = tf.placeholder(shape=(None, n_y), dtype=tf.float32)

    return X, Y


# - **Forward propagation**

# In[15]:


def forward_propagation(X, parameters=None):
    """
    Implements the forward propagation for the model:
    CONV3D -> CONV3D -> MAXPOOL -> CONV3D -> CONV3D -> MAXPOOL -> CONV3D -> CONV3D -> MAXPOOL -> CONV3D -> CONV3D -> MAXPOOL -> 
    CONV3D -> CONV3D -> MAXPOOL -> CONV3D -> CONV3D -> MAXPOOL -> FLATTEN -> FULLYCONNECTED -> FULLYCONNECTED -> FULLYCONNECTED

    Arguments:
    X -- input dataset placeholder, of shape (input size, number of examples)
    parameters -- python dictionary containing your parameters "W1", "W2"
                  the shapes are given in initialize_parameters

    Returns:
    Z3 -- the output of the last LINEAR unit
    """

    # CONV3D: number of filters in total 64, stride 1, padding 'SAME', activation 'relu', kernel parameter initializer 'xavier'
    # output_size = (batch_size, 256, 256, 256, 64)
    A11 = tf.layers.conv3d(X, filters=64, kernel_size=3, strides=1, padding="SAME",
                          activation=tf.nn.relu, kernel_initializer=tf.contrib.layers.xavier_initializer(seed=0))
    
    # CONV3D: number of filters in total 64, stride 1, padding 'SAME', activation 'relu', kernel parameter initializer 'xavier'
    # output_size = (batch_size, 256, 256, 256, 64)
    A12 = tf.layers.conv3d(A11, filters=64, kernel_size=3, strides=1, padding="SAME",
                          activation=tf.nn.relu, kernel_initializer=tf.contrib.layers.xavier_initializer(seed=0))

    # MAXPOOL: window 3x3x3, sride 2, padding 'SAME'
    # output_size = (batch_size, 128, 128, 128, 64)
    P1 = tf.layers.max_pooling3d(A12, pool_size=3, strides=2, padding="SAME")

    
    
    # CONV3D: number of filters in total 128, stride 1, padding 'SAME', activation 'relu', kernel parameter initializer 'xavier'
    # output_size = (batch_size, 128, 128, 128, 128)
    A21 = tf.layers.conv3d(P1, filters=128, kernel_size=3, strides=1, padding="SAME",
                          activation=tf.nn.relu, kernel_initializer=tf.contrib.layers.xavier_initializer(seed=0))
    
    # CONV3D: number of filters in total 128, stride 1, padding 'SAME', activation 'relu', kernel parameter initializer 'xavier'
    # output_size = (batch_size, 128, 128, 128, 128)
    A22 = tf.layers.conv3d(A21, filters=128, kernel_size=3, strides=1, padding="SAME",
                          activation=tf.nn.relu, kernel_initializer=tf.contrib.layers.xavier_initializer(seed=0))

    # MAXPOOL: window 3x3x3, stride 2, padding 'SAME'
    # output_size = (batch_size, 64, 64, 64, 128)
    P2 = tf.layers.max_pooling3d(A22, pool_size=3, strides=2, padding="SAME")
    
    
    
    # CONV3D: number of filters in total 256, stride 1, padding 'SAME', activation 'relu', kernel parameter initializer 'xavier'
    # output_size = (batch_size, 64, 64, 64, 256)
    A31 = tf.layers.conv3d(P2, filters=256, kernel_size=3, strides=1, padding="SAME",
                          activation=tf.nn.relu, kernel_initializer=tf.contrib.layers.xavier_initializer(seed=0))
    
    # CONV3D: number of filters in total 256, stride 1, padding 'SAME', activation 'relu', kernel parameter initializer 'xavier'
    # output_size = (batch_size, 64, 64, 64, 256)
    A32 = tf.layers.conv3d(A31, filters=256, kernel_size=3, strides=1, padding="SAME",
                          activation=tf.nn.relu, kernel_initializer=tf.contrib.layers.xavier_initializer(seed=0))

    # MAXPOOL: window 3x3x3, stride 2, padding 'SAME'
    # output_size = (batch_size, 32, 32, 32, 256)
    P3 = tf.layers.max_pooling3d(A32, pool_size=3, strides=2, padding="SAME")
    
    
    
    # CONV3D: number of filters in total 512, stride 1, padding 'SAME', activation 'relu', kernel parameter initializer 'xavier'
    # output_size = (batch_size, 32, 32, 32, 512)
    A41 = tf.layers.conv3d(P3, filters=512, kernel_size=3, strides=1, padding="SAME",
                          activation=tf.nn.relu, kernel_initializer=tf.contrib.layers.xavier_initializer(seed=0))
    
    # CONV3D: number of filters in total 512, stride 1, padding 'SAME', activation 'relu', kernel parameter initializer 'xavier'
    # output_size = (batch_size, 32, 32, 32, 512)
    A42 = tf.layers.conv3d(A41, filters=512, kernel_size=3, strides=1, padding="SAME",
                          activation=tf.nn.relu, kernel_initializer=tf.contrib.layers.xavier_initializer(seed=0))

    # MAXPOOL: window 3x3x3, stride 2, padding 'SAME'
    # output_size = (batch_size, 16, 16, 16, 512)
    P4 = tf.layers.max_pooling3d(A42, pool_size=3, strides=2, padding="SAME")
    
    

    # CONV3D: number of filters in total 512, stride 1, padding 'SAME', activation 'relu', kernel parameter initializer 'xavier'
    # output_size = (batch_size, 16, 16, 16, 512)
    A51 = tf.layers.conv3d(P4, filters=512, kernel_size=3, strides=1, padding="SAME",
                          activation=tf.nn.relu, kernel_initializer=tf.contrib.layers.xavier_initializer(seed=0))
    
    # CONV3D: number of filters in total 512, stride 1, padding 'SAME', activation 'relu', kernel parameter initializer 'xavier'
    # output_size = (batch_size, 16, 16, 16, 512)
    A52 = tf.layers.conv3d(A51, filters=512, kernel_size=3, strides=1, padding="SAME",
                          activation=tf.nn.relu, kernel_initializer=tf.contrib.layers.xavier_initializer(seed=0))

    # MAXPOOL: window 3x3x3, stride 2, padding 'SAME'
    # output_size = (batch_size, 8, 8, 8, 512)
    P5 = tf.layers.max_pooling3d(A52, pool_size=3, strides=2, padding="SAME")
    
    
    # CONV3D: number of filters in total 512, stride 1, padding 'SAME', activation 'relu', kernel parameter initializer 'xavier'
    # output_size = (batch_size, 8, 8, 8, 512)
    A61 = tf.layers.conv3d(P5, filters=512, kernel_size=3, strides=1, padding="SAME",
                          activation=tf.nn.relu, kernel_initializer=tf.contrib.layers.xavier_initializer(seed=0))
    
    # CONV3D: number of filters in total 512, stride 1, padding 'SAME', activation 'relu', kernel parameter initializer 'xavier'
    # output_size = (batch_size, 8, 8, 8, 512)
    A62 = tf.layers.conv3d(A61, filters=512, kernel_size=3, strides=1, padding="SAME",
                          activation=tf.nn.relu, kernel_initializer=tf.contrib.layers.xavier_initializer(seed=0))

    # MAXPOOL: window 3x3x3, stride 2, padding 'SAME'
    # output_size = (batch_size, 4, 4, 4, 512)
    P6 = tf.layers.max_pooling3d(A62, pool_size=3, strides=2, padding="SAME")
    
    
    
    # FLATTEN
    # output_size = (batch_size, 32768)
    P6 = tf.contrib.layers.flatten(P6)

    # FULLY-CONNECTED without non-linear activation function (do not call softmax).
    # 4096 neurons in output layer. Hint: one of the arguments should be "activation_fn=None"
    # output_size = (batch_size,4096)
    Z1 = tf.contrib.layers.fully_connected(P6, 4096, activation_fn=None)
    
    # FULLY-CONNECTED without non-linear activation function (do not call softmax).
    # 4096 neurons in output layer. Hint: one of the arguments should be "activation_fn=None"
    # output_size = (batch_size,4096)
    Z2 = tf.contrib.layers.fully_connected(Z1, 4096, activation_fn=None)
    
    # FULLY-CONNECTED without non-linear activation function (do not call softmax).
    # 5 neurons in output layer. Hint: one of the arguments should be "activation_fn=None"
    # output_size = (batch_size,5)
    Z3 = tf.contrib.layers.fully_connected(Z2, 5, activation_fn=None)

    return Z3


# - **compute cost**

# In[16]:


def compute_cost(Z3, Y):
    """
    Computes the cost

    Arguments:
    Z3 -- output of forward propagation (output of the last LINEAR unit), of shape (number of examples, n_y)
    Y -- "true" labels vector placeholder, same shape as Z3

    Returns:
    cost - Tensor of the cost function
    """

    cost = tf.nn.softmax_cross_entropy_with_logits(logits=Z3, labels=Y)
    cost = tf.reduce_mean(cost)

    return cost


# - **mini-batch**

# In[17]:


def random_mini_batches(X, Y, mini_batch_size=50, seed=0):
    """
    Creates a list of random minibatches from (X, Y)

    Arguments:
    X -- input data, of shape (input size, n_D0, n_H0, n_W0, n_C0)
    Y -- true "label" vector (1 for blue dot / 0 for red dot), of shape (1, number of examples)
    mini_batch_size -- size of the mini-batches, integer

    Returns:
    mini_batches -- list of synchronous (mini_batch_X, mini_batch_Y)
    """

    # To make your "random" minibatches the same as ours
    np.random.seed(seed)
    m = X.shape[0]                  # number of training examples
    mini_batches = []

    # Step 1: Shuffle (X, Y)
    permutation = np.random.permutation(m)
    shuffled_X = X[permutation]
    shuffled_Y = Y[permutation]

    # Step 2: Partition (shuffled_X, shuffled_Y). Minus the end case.
    # number of mini batches of size mini_batch_size in your partitionning
    num_complete_minibatches = math.floor(m/mini_batch_size)
    for k in range(0, num_complete_minibatches):
        mini_batch_X = shuffled_X[k*mini_batch_size:(k+1)*mini_batch_size]
        mini_batch_Y = shuffled_Y[k*mini_batch_size:(k+1)*mini_batch_size]
        mini_batch = (mini_batch_X, mini_batch_Y)
        mini_batches.append(mini_batch)

    # Handling the end case (last mini-batch < mini_batch_size)
    if m % mini_batch_size != 0:
        mini_batch_X = shuffled_X[num_complete_minibatches*mini_batch_size:]
        mini_batch_Y = shuffled_Y[num_complete_minibatches*mini_batch_size:]
        mini_batch = (mini_batch_X, mini_batch_Y)
        mini_batches.append(mini_batch)

    return mini_batches


# - **model**

# In[18]:


def model(X_train, Y_train, X_test, Y_test, learning_rate=0.009,
          num_epochs=3, minibatch_size=1, print_cost=True):
    """
    Implements a three-layer ConvNet in Tensorflow:
    CONV3D -> CONV3D -> MAXPOOL -> CONV3D -> CONV3D -> MAXPOOL -> CONV3D -> CONV3D -> MAXPOOL -> CONV3D -> CONV3D -> MAXPOOL -> 
    CONV3D -> CONV3D -> MAXPOOL -> CONV3D -> CONV3D -> MAXPOOL -> FLATTEN -> FULLYCONNECTED -> FULLYCONNECTED -> FULLYCONNECTED

    Arguments:
    X_train -- training set, of shape (None, 256 256, 256, 1)
    Y_train -- test set, of shape (None, n_y = 5)
    X_test -- training set, of shape (None, 256, 256, 256, 1)
    Y_test -- test set, of shape (None, n_y = 5)
    learning_rate -- learning rate of the optimization
    num_epochs -- number of epochs of the optimization loop
    minibatch_size -- size of a minibatch
    print_cost -- True to print the cost every 100 epochs

    Returns:
    train_accuracy -- real number, accuracy on the train set (X_train)
    test_accuracy -- real number, testing accuracy on the test set (X_test)
    parameters -- parameters learnt by the model. They can then be used to predict.
    """

    # to be able to rerun the model without overwriting tf variables
    ops.reset_default_graph()
    # to keep results consistent (tensorflow seed)
    tf.set_random_seed(1)
    # to keep results consistent (numpy seed)
    seed = 3
    (m, n_D0, n_H0, n_W0, n_C0) = X_train.shape
    n_y = Y_train.shape[1]
    # To keep track of the cost
    costs = []                          

    # Create Placeholders of the correct shape
    X, Y = create_placeholders(n_D0, n_H0, n_W0, n_C0, n_y)

    # Forward propagation: Build the forward propagation in the tensorflow graph
    Z3 = forward_propagation(X)

    # Cost function: Add cost function to tensorflow graph
    cost = compute_cost(Z3, Y)

    # Backpropagation: Define the tensorflow optimizer. Use an AdamOptimizer that minimizes the cost.
    optimizer = tf.train.AdamOptimizer(learning_rate).minimize(cost)

    # Initialize all the variables globally
    init = tf.global_variables_initializer()

    # Start the session to compute the tensorflow graph
    with tf.Session() as sess:

        # Run the initialization
        sess.run(init)

        # Do the training loop
        for epoch in range(num_epochs):

            minibatch_cost = 0.
            # number of minibatches of size minibatch_size in the train set
            num_minibatches = int(m / minibatch_size)
            seed = seed + 1
            minibatches = random_mini_batches(
                X_train, Y_train, minibatch_size, seed)

            for minibatch in minibatches:

                # Select a minibatch
                (minibatch_X, minibatch_Y) = minibatch
                # Run the session to execute the optimizer and the cost
                # The feedict should contain a minibatch for (X,Y).
                _, temp_cost = sess.run([optimizer, cost], feed_dict={
                                        X: minibatch_X, Y: minibatch_Y})

                minibatch_cost += temp_cost / num_minibatches

            # Print the cost every epoch
            if print_cost == True and epoch % 1 == 0:
                print("Cost after epoch %i: %f" % (epoch, minibatch_cost))
            if print_cost == True and epoch % 1 == 0:
                costs.append(minibatch_cost)

        # plot the cost
        plt.plot(np.squeeze(costs))
        plt.ylabel('cost')
        plt.xlabel('iterations (per tens)')
        plt.title("Learning rate =" + str(learning_rate))
        plt.show()

        # Calculate the correct predictions
        predict_op = tf.argmax(Z3, 1)
        correct_prediction = tf.equal(predict_op, tf.argmax(Y, 1))

        # Calculate accuracy on the test set
        accuracy = tf.reduce_mean(tf.cast(correct_prediction, "float"))
        print(accuracy)
        train_accuracy = accuracy.eval({X: X_train, Y: Y_train})
        test_accuracy = accuracy.eval({X: X_test, Y: Y_test})
        print("Train Accuracy:", train_accuracy)
        print("Test Accuracy:", test_accuracy)

        return train_accuracy, test_accuracy


# In[19]:


_, _ = model(X_train, Y_train, X_test, Y_test, num_epochs=3, minibatch_size=1)

